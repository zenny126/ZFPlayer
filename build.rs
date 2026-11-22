use std::env;
use std::fmt::Write as _;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    #[cfg(windows)]
    {
        println!("cargo:rerun-if-changed=app_icon.ico");
        let mut res = winres::WindowsResource::new();
        if std::path::Path::new("app_icon.ico").exists() {
            res.set_icon("app_icon.ico");
        }
        res.set("ProductName", "ZFPlayer");
        res.set("FileDescription", "ZFPlayer - Hi-Res Lossless Audio Player");
        res.set("LegalCopyright", "Copyright (c) 2026 Zenny");
        res.compile().expect("Failed to compile Windows resources");

        // `lld` drops unreferenced static archives (`libresource.a`); link `resource.o` directly
        // so `.rsrc` (app icon + version metadata) is always embedded in the final PE binary.
        if env::var("CARGO_CFG_TARGET_ENV").as_deref() != Ok("msvc") {
            let resource_obj = PathBuf::from(env::var("OUT_DIR").unwrap()).join("resource.o");
            if resource_obj.exists() {
                println!("cargo:rustc-link-arg={}", resource_obj.display());
            }
        }

        build_static_webview2_shim();
    }
}

#[cfg(windows)]
fn build_static_webview2_shim() {
    let target_os = env::var("CARGO_CFG_TARGET_OS").unwrap_or_default();
    let target_env = env::var("CARGO_CFG_TARGET_ENV").unwrap_or_default();
    let target_arch = env::var("CARGO_CFG_TARGET_ARCH").unwrap_or_default();

    if target_os != "windows" || target_env == "msvc" || target_arch != "x86_64" {
        return;
    }

    let manifest_dir = PathBuf::from(env::var("CARGO_MANIFEST_DIR").unwrap());
    let dll_path = manifest_dir.join("vendor").join("x64").join("WebView2Loader.dll");
    println!("cargo:rerun-if-changed={}", dll_path.display());

    let Ok(dll_bytes) = fs::read(&dll_path) else {
        panic!("Missing vendored WebView2Loader.dll at {:?}", dll_path);
    };

    let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
    let shim_dir = out_dir.join("wv2_shim");
    fs::create_dir_all(&shim_dir).expect("Failed to create wv2_shim directory");

    let mut hex_buf = String::with_capacity(dll_bytes.len() * 4);
    for (idx, b) in dll_bytes.iter().enumerate() {
        if idx > 0 {
            hex_buf.push(',');
        }
        if idx % 32 == 0 {
            hex_buf.push('\n');
        }
        let _ = write!(hex_buf, "0x{:02x}", b);
    }

    let c_src = format!(
        r#"#include <windows.h>

static const unsigned char WV2_DLL_BYTES[{len}] = {{ {hex}
}};
static volatile HMODULE g_wv2_mod = NULL;

static HMODULE get_wv2_module(void) {{
    HMODULE mod = g_wv2_mod;
    if (mod) return mod;

    WCHAR temp_path[MAX_PATH];
    DWORD len = GetTempPathW(MAX_PATH, temp_path);
    if (len == 0 || len > MAX_PATH - 64) return NULL;

    WCHAR dll_path[MAX_PATH];
    wsprintfW(dll_path, L"%sZFPlayer_WebView2Loader_x64.dll", temp_path);

    DWORD expected_size = (DWORD)sizeof(WV2_DLL_BYTES);
    WIN32_FILE_ATTRIBUTE_DATA fad;
    BOOL needs_write = TRUE;
    if (GetFileAttributesExW(dll_path, GetFileExInfoStandard, &fad)) {{
        if (fad.nFileSizeHigh == 0 && fad.nFileSizeLow == expected_size) {{
            needs_write = FALSE;
        }}
    }}

    if (needs_write) {{
        WCHAR tmp_path[MAX_PATH];
        DWORD pid = GetCurrentProcessId();
        wsprintfW(tmp_path, L"%sZFPlayer_WebView2Loader_x64_%lu.tmp", temp_path, (unsigned long)pid);

        HANDLE hFile = CreateFileW(
            tmp_path,
            GENERIC_WRITE,
            FILE_SHARE_READ,
            NULL,
            CREATE_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );
        if (hFile != INVALID_HANDLE_VALUE) {{
            DWORD total_written = 0;
            while (total_written < expected_size) {{
                DWORD chunk = 0;
                if (!WriteFile(hFile, WV2_DLL_BYTES + total_written, expected_size - total_written, &chunk, NULL) || chunk == 0) {{
                    break;
                }}
                total_written += chunk;
            }}
            CloseHandle(hFile);
            if (total_written == expected_size) {{
                if (!MoveFileExW(tmp_path, dll_path, MOVEFILE_REPLACE_EXISTING)) {{
                    mod = LoadLibraryW(dll_path);
                    if (!mod) {{
                        mod = LoadLibraryW(tmp_path);
                    }} else {{
                        DeleteFileW(tmp_path);
                    }}
                    if (mod) {{
                        g_wv2_mod = mod;
                        return mod;
                    }}
                }}
            }} else {{
                DeleteFileW(tmp_path);
            }}
        }}
    }}

    mod = LoadLibraryW(dll_path);
    if (mod) {{
        g_wv2_mod = mod;
    }}
    return mod;
}}

typedef HRESULT (WINAPI *PFN_CompareBrowserVersions)(PCWSTR, PCWSTR, int*);
typedef HRESULT (WINAPI *PFN_CreateCoreWebView2Environment)(void*);
typedef HRESULT (WINAPI *PFN_CreateCoreWebView2EnvironmentWithOptions)(PCWSTR, PCWSTR, void*, void*);
typedef HRESULT (WINAPI *PFN_GetAvailableCoreWebView2BrowserVersionString)(PCWSTR, PWSTR*);

HRESULT WINAPI CompareBrowserVersions(PCWSTR v1, PCWSTR v2, int* result) {{
    HMODULE m = get_wv2_module();
    if (!m) return E_FAIL;
    PFN_CompareBrowserVersions fn = (PFN_CompareBrowserVersions)(void*)GetProcAddress(m, "CompareBrowserVersions");
    return fn ? fn(v1, v2, result) : E_FAIL;
}}

HRESULT WINAPI CreateCoreWebView2Environment(void* handler) {{
    HMODULE m = get_wv2_module();
    if (!m) return E_FAIL;
    PFN_CreateCoreWebView2Environment fn = (PFN_CreateCoreWebView2Environment)(void*)GetProcAddress(m, "CreateCoreWebView2Environment");
    return fn ? fn(handler) : E_FAIL;
}}

HRESULT WINAPI CreateCoreWebView2EnvironmentWithOptions(PCWSTR brFolder, PCWSTR udFolder, void* opts, void* handler) {{
    HMODULE m = get_wv2_module();
    if (!m) return E_FAIL;
    PFN_CreateCoreWebView2EnvironmentWithOptions fn = (PFN_CreateCoreWebView2EnvironmentWithOptions)(void*)GetProcAddress(m, "CreateCoreWebView2EnvironmentWithOptions");
    return fn ? fn(brFolder, udFolder, opts, handler) : E_FAIL;
}}

HRESULT WINAPI GetAvailableCoreWebView2BrowserVersionString(PCWSTR brFolder, PWSTR* verInfo) {{
    HMODULE m = get_wv2_module();
    if (!m) return E_FAIL;
    PFN_GetAvailableCoreWebView2BrowserVersionString fn = (PFN_GetAvailableCoreWebView2BrowserVersionString)(void*)GetProcAddress(m, "GetAvailableCoreWebView2BrowserVersionString");
    return fn ? fn(brFolder, verInfo) : E_FAIL;
}}
"#,
        len = dll_bytes.len(),
        hex = hex_buf
    );

    let shim_c = shim_dir.join("wv2_static_shim.c");
    fs::write(&shim_c, c_src).expect("Failed to write wv2_static_shim.c");

    cc::Build::new()
        .file(&shim_c)
        .opt_level(2)
        .out_dir(&shim_dir)
        .cargo_metadata(false)
        .warnings(false)
        .compile("wv2_static_shim");

    let built_a = shim_dir.join("libwv2_static_shim.a");
    if !built_a.exists() {
        panic!("Expected static shim archive at {:?} was not created", built_a);
    }

    let target_a = shim_dir.join("libWebView2Loader.dll.a");
    let target_lib = shim_dir.join("WebView2Loader.dll.lib");
    fs::copy(&built_a, &target_a).expect("Failed to copy shim to libWebView2Loader.dll.a");
    fs::copy(&built_a, &target_lib).expect("Failed to copy shim to WebView2Loader.dll.lib");

    stage_static_libunwind(&shim_dir);

    println!("cargo:rustc-link-search=native={}", shim_dir.display());
}

/// Shadow system `libunwind.dll.a` inside `shim_dir` so `rustc`'s `-lunwind` flag
/// always resolves to the static archive on unmodified `llvm-mingw` toolchains.
#[cfg(windows)]
fn stage_static_libunwind(shim_dir: &Path) {
    let compiler_path = cc::Build::new().get_compiler().path().to_path_buf();
    let candidates = [
        compiler_path,
        PathBuf::from("x86_64-w64-mingw32-clang"),
        PathBuf::from("clang"),
    ];

    for cmd in &candidates {
        let Ok(out) = Command::new(cmd)
            .arg("--print-file-name=libunwind.a")
            .output()
        else {
            continue;
        };
        if !out.status.success() {
            continue;
        }
        let resolved = PathBuf::from(String::from_utf8_lossy(&out.stdout).trim());
        if resolved.is_file() {
            fs::copy(&resolved, shim_dir.join("libunwind.dll.a"))
                .expect("Failed to copy static libunwind.a as libunwind.dll.a");
            fs::copy(&resolved, shim_dir.join("libunwind.a"))
                .expect("Failed to copy static libunwind.a");
            return;
        }
    }
}

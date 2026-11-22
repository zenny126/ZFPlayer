use std::env;
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

fn main() {
    #[cfg(windows)]
    {
        println!("cargo:rerun-if-changed=app_icon.ico");
        let mut res = winres::WindowsResource::new();
        if Path::new("app_icon.ico").exists() {
            res.set_icon("app_icon.ico");
        }
        res.set("ProductName", "ZFPlayer");
        res.set(
            "FileDescription",
            "ZFPlayer - Native Rust Hi-Res Lossless Audio Player",
        );
        res.set("LegalCopyright", "Copyright (c) 2026 Zenny");
        res.compile().expect("Failed to compile Windows resources");

        // `lld` drops unreferenced static archives (`libresource.a`); link `resource.o` directly
        // so `.rsrc` (app icon + version metadata) is always embedded in the final PE binary.
        if env::var("CARGO_CFG_TARGET_ENV").as_deref() != Ok("msvc") {
            let out_dir = PathBuf::from(env::var("OUT_DIR").unwrap());
            let resource_obj = out_dir.join("resource.o");
            if resource_obj.exists() {
                println!("cargo:rustc-link-arg={}", resource_obj.display());
            }
            stage_static_libunwind(&out_dir);
        }
    }
}

/// Shadow system `libunwind.dll.a` so `rustc`'s `-lunwind` flag always links statically
/// against `libunwind.a` on unmodified `llvm-mingw` toolchains (0 external DLL dependencies).
#[cfg(windows)]
fn stage_static_libunwind(out_dir: &Path) {
    let lib_dir = out_dir.join("static_libs");
    let _ = fs::create_dir_all(&lib_dir);

    for cmd in ["x86_64-w64-mingw32-clang", "clang"] {
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
            fs::copy(&resolved, lib_dir.join("libunwind.dll.a"))
                .expect("Failed to copy static libunwind.a as libunwind.dll.a");
            fs::copy(&resolved, lib_dir.join("libunwind.a"))
                .expect("Failed to copy static libunwind.a");
            println!("cargo:rustc-link-search=native={}", lib_dir.display());
            return;
        }
    }
}

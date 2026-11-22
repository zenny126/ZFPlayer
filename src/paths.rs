use std::env;
use std::fs;
use std::path::PathBuf;

/// Returns the base directory for frontend assets (`frontend/`).
pub fn get_frontend_dir() -> PathBuf {
    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            let beside_exe = exe_dir.join("frontend");
            if beside_exe.exists() {
                return beside_exe;
            }
            // If running inside target/debug or target/release
            if let Some(parent) = exe_dir.parent().and_then(|p| p.parent()) {
                let in_project = parent.join("frontend");
                if in_project.exists() {
                    return in_project;
                }
            }
        }
    }

    let cwd_frontend = env::current_dir()
        .unwrap_or_else(|_| PathBuf::from("."))
        .join("frontend");
    if cwd_frontend.exists() {
        return cwd_frontend;
    }

    PathBuf::from("frontend")
}

/// Returns the writable directory for app data (config, db, cache).
/// Prefers portable data next to the executable if present, then project root in dev mode,
/// then `%APPDATA%/ZFPlayer`.
pub fn get_app_data_dir() -> PathBuf {
    let data_dir = resolve_base_data_dir();
    let _ = fs::create_dir_all(&data_dir);
    data_dir
}

fn resolve_base_data_dir() -> PathBuf {
    if let Ok(exe_path) = env::current_exe() {
        if let Some(exe_dir) = exe_path.parent() {
            // Check portable mode markers right next to executable
            let is_portable = exe_dir.join("data").exists()
                || exe_dir.join("config").exists()
                || exe_dir.join("portable").exists()
                || exe_dir.join("portable.txt").exists();
            if is_portable {
                return exe_dir.to_path_buf();
            }

            // Check if running inside target/debug or target/release of zfplayer-rust
            if let Some(project_root) = exe_dir.parent().and_then(|p| p.parent()) {
                if project_root.join("Cargo.toml").exists() {
                    return project_root.to_path_buf();
                }
            }

            // Check if parent directory has data/library.db or config/config.json (like dist/)
            if let Some(parent_dir) = exe_dir.parent() {
                if parent_dir.join("data").join("library.db").exists()
                    || parent_dir.join("config").join("config.json").exists()
                {
                    return parent_dir.to_path_buf();
                }
            }
        }
    }

    if let Ok(cwd) = env::current_dir() {
        if cwd.join("Cargo.toml").exists() {
            return cwd;
        }
    }

    if let Ok(appdata) = env::var("APPDATA") {
        return PathBuf::from(appdata).join("ZFPlayer");
    }

    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

pub fn get_config_path() -> PathBuf {
    let path = get_app_data_dir().join("config").join("config.json");
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    path
}

pub fn get_db_path() -> PathBuf {
    let path = get_app_data_dir().join("data").join("library.db");
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    path
}

pub fn get_cache_dir() -> PathBuf {
    let path = get_app_data_dir().join("cache");
    let _ = fs::create_dir_all(&path);
    path
}

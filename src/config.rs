use serde_json::{json, Map, Value};
use std::fs;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::Duration;

use crate::paths::get_config_path;

#[derive(Clone)]
pub struct Config {
    config_path: PathBuf,
    data: Arc<Mutex<Map<String, Value>>>,
    save_lock: Arc<Mutex<()>>,
}

impl Config {
    pub fn new() -> Self {
        Self::new_at(get_config_path())
    }

    pub fn new_at(config_path: PathBuf) -> Self {
        let cfg = Self {
            config_path,
            data: Arc::new(Mutex::new(Map::new())),
            save_lock: Arc::new(Mutex::new(())),
        };
        cfg.load();
        cfg
    }

    fn default_config() -> Map<String, Value> {
        let mut m = Map::new();
        m.insert("music_dirs".to_string(), json!([]));
        m.insert("volume".to_string(), json!(0.8));
        m.insert("repeat".to_string(), json!("off"));
        m.insert("shuffle".to_string(), json!(false));
        m.insert("theme".to_string(), json!("dark"));
        m.insert("last_track".to_string(), Value::Null);
        m.insert("last_position".to_string(), json!(0));
        m.insert("audio_mode".to_string(), json!("shared"));
        m.insert("shortcuts".to_string(), json!({}));
        m
    }

    pub fn load(&self) {
        let mut merged = Self::default_config();
        let mut existed = false;

        if self.config_path.exists() {
            if let Ok(content) = fs::read_to_string(&self.config_path) {
                if let Ok(Value::Object(parsed)) = serde_json::from_str::<Value>(&content) {
                    for (k, v) in parsed {
                        merged.insert(k, v);
                    }
                    existed = true;
                }
            }
        }

        if let Ok(mut guard) = self.data.lock() {
            *guard = merged;
        }

        if !existed {
            self.save_sync();
        }
    }

    pub fn get(&self, key: &str) -> Option<Value> {
        self.data
            .lock()
            .ok()
            .and_then(|guard| guard.get(key).cloned())
    }

    pub fn get_f64(&self, key: &str, default: f64) -> f64 {
        self.get(key).and_then(|v| v.as_f64()).unwrap_or(default)
    }

    pub fn get_bool(&self, key: &str, default: bool) -> bool {
        self.get(key).and_then(|v| v.as_bool()).unwrap_or(default)
    }

    pub fn get_string(&self, key: &str, default: &str) -> String {
        self.get(key)
            .and_then(|v| v.as_str().map(|s| s.to_string()))
            .unwrap_or_else(|| default.to_string())
    }

    pub fn get_string_vec(&self, key: &str) -> Vec<String> {
        self.get(key)
            .and_then(|v| v.as_array().cloned())
            .map(|arr| {
                arr.into_iter()
                    .filter_map(|x| x.as_str().map(|s| s.to_string()))
                    .collect()
            })
            .unwrap_or_default()
    }

    /// Update in-memory configuration without immediate disk I/O (used by debounced sliders).
    pub fn set_in_memory(&self, key: &str, value: Value) {
        if let Ok(mut guard) = self.data.lock() {
            guard.insert(key.to_string(), value);
        }
    }

    pub fn set(&self, key: &str, value: Value) {
        self.set_in_memory(key, value);
        self.save_sync();
    }

    pub fn get_all(&self) -> Value {
        if let Ok(guard) = self.data.lock() {
            Value::Object(guard.clone())
        } else {
            Value::Object(Self::default_config())
        }
    }

    pub fn save_sync(&self) {
        let Ok(_save_guard) = self.save_lock.lock() else {
            return;
        };
        if let Some(parent) = self.config_path.parent() {
            let _ = fs::create_dir_all(parent);
        }
        let temp_path = self.config_path.with_extension("json.tmp");
        let snapshot = self.get_all();
        if let Ok(serialized) = serde_json::to_string_pretty(&snapshot) {
            if fs::write(&temp_path, serialized).is_ok() {
                if fs::rename(&temp_path, &self.config_path).is_err() {
                    thread::sleep(Duration::from_millis(10));
                    if fs::rename(&temp_path, &self.config_path).is_err() {
                        let _ = fs::copy(&temp_path, &self.config_path);
                        let _ = fs::remove_file(&temp_path);
                    }
                }
            }
        }
    }
}

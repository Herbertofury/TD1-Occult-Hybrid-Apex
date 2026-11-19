//! The in-game build has no HTTP dependency or provider credentials. All calls
//! below belong to the DLL's existing background query worker, never GFx.
use crate::catalog::{Catalog, Query};
use serde_json::{Value, json};
use std::{
    ffi::{CStr, CString, c_char, c_void},
    path::Path,
    ptr,
    sync::Mutex,
};

struct Handle(Mutex<Catalog>);
fn reply(value: Value) -> *mut c_char {
    let raw = serde_json::to_string(&value).unwrap_or_else(|_| "{\"ok\":false}".into());
    CString::new(raw).map_or(ptr::null_mut(), CString::into_raw)
}
#[unsafe(no_mangle)]
pub extern "C" fn ApexCatalogVersion() -> u32 {
    2
}

/// # Safety
/// Like Open, with three additional valid NUL-terminated UTF-8 strings. This
/// binds exactly one save and immutable equipped snapshot before any query.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexCatalogOpenUsage(
    path: *const c_char,
    sha: *const c_char,
    usage: *const c_char,
    usage_sha: *const c_char,
    save: *const c_char,
) -> *mut c_void {
    if [path, sha, usage, usage_sha, save]
        .iter()
        .any(|p| p.is_null())
    {
        return ptr::null_mut();
    }
    std::panic::catch_unwind(|| -> Option<*mut c_void> {
        let read = |p| unsafe { CStr::from_ptr(p) }.to_str().ok();
        let (path, sha, usage, usage_sha, save) = (
            read(path)?,
            read(sha)?,
            read(usage)?,
            read(usage_sha)?,
            read(save)?,
        );
        if path.len() > 32768
            || usage.len() > 32768
            || sha.len() != 64
            || usage_sha.len() != 64
            || save.len() > 20
        {
            return None;
        }
        let c = Catalog::open(Path::new(path), sha)
            .ok()?
            .with_usage(Path::new(usage), usage_sha, save)
            .ok()?;
        Some(Box::into_raw(Box::new(Handle(Mutex::new(c)))).cast())
    })
    .ok()
    .flatten()
    .unwrap_or(ptr::null_mut())
}

/// # Safety
/// Inputs must be valid NUL-terminated UTF-8 strings for the duration of this
/// call. The returned opaque handle is owned by the caller until Close.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexCatalogOpen(
    path: *const c_char,
    sha256: *const c_char,
) -> *mut c_void {
    if path.is_null() || sha256.is_null() {
        return ptr::null_mut();
    }
    std::panic::catch_unwind(|| {
        let path = unsafe { CStr::from_ptr(path) }.to_str().ok()?;
        let sha = unsafe { CStr::from_ptr(sha256) }.to_str().ok()?;
        if path.len() > 32768 || sha.len() != 64 {
            return None;
        }
        let catalog = Catalog::open(Path::new(path), sha).ok()?;
        Some(Box::into_raw(Box::new(Handle(Mutex::new(catalog)))).cast())
    })
    .ok()
    .flatten()
    .unwrap_or(ptr::null_mut())
}

/// # Safety
/// `handle` must be a live handle from Open, and query must point to exactly
/// `bytes` readable UTF-8 bytes. Free the independent returned allocation once.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexCatalogQuery(
    handle: *mut c_void,
    query: *const u8,
    bytes: usize,
) -> *mut c_char {
    if handle.is_null() || query.is_null() || bytes > 2048 {
        return reply(json!({"ok":false,"message":"Invalid bounded offline query"}));
    }
    let result =
        std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> anyhow::Result<Value> {
            let raw = unsafe { std::slice::from_raw_parts(query, bytes) };
            let value: Value = serde_json::from_slice(raw)?;
            let parsed: Query = serde_json::from_value(value.clone())?;
            let state = unsafe { &*handle.cast::<Handle>() };
            let mut result = state
                .0
                .lock()
                .map_err(|_| anyhow::anyhow!("Offline query lock failed"))?
                .query(&parsed)?;
            result["query"] = value;
            anyhow::ensure!(
                serde_json::to_vec(&result)?.len()
                    <= if parsed.limit <= 24 {
                        120 * 1024
                    } else {
                        512 * 1024
                    },
                "Offline page exceeds its bound"
            );
            Ok(result)
        }));
    match result {
        Ok(Ok(value)) => reply(value),
        Ok(Err(error)) => reply(json!({"ok":false,"message":error.to_string()})),
        Err(_) => reply(json!({"ok":false,"message":"Offline metadata query failed"})),
    }
}

/// # Safety
/// The argument must be null or the still-owned return from ApexCatalogQuery.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexCatalogFree(value: *mut c_char) {
    if !value.is_null() {
        drop(unsafe { CString::from_raw(value) });
    }
}
/// # Safety
/// Close a live Open handle exactly once, after all its queries have finished.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn ApexCatalogClose(handle: *mut c_void) {
    if !handle.is_null() {
        drop(unsafe { Box::from_raw(handle.cast::<Handle>()) });
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn invalid_abi_inputs_are_typed_failures() {
        unsafe {
            assert!(ApexCatalogOpen(ptr::null(), ptr::null()).is_null());
            let p = ApexCatalogQuery(ptr::null_mut(), ptr::null(), 0);
            assert!(!p.is_null());
            let v: Value = serde_json::from_slice(CStr::from_ptr(p).to_bytes()).unwrap();
            assert_eq!(v["ok"], false);
            ApexCatalogFree(p);
            ApexCatalogFree(ptr::null_mut());
            ApexCatalogClose(ptr::null_mut());
        }
    }
}

//! Нормализация текста и MD5-хэш для ключей кэша эмбеддингов.
//! Поведение совместимо с Python: ' '.join(text.lower().split()) + hashlib.md5(...).hexdigest()

use faster_hex::hex_string;
use pyo3::prelude::*;

/// Нормализует текст: нижний регистр, схлопывание пробелов в один пробел.
/// Эквивалент Python: ' '.join(text.lower().split())
/// Одна аллокация под результат (без Vec промежуточных срезов).
#[inline]
fn normalize(text: &str) -> String {
    let lower = text.to_lowercase();
    let mut out = String::with_capacity(lower.len());
    let mut first = true;
    for word in lower.split_whitespace() {
        if !first {
            out.push(' ');
        }
        out.push_str(word);
        first = false;
    }
    out
}

/// Возвращает MD5-хэш нормализованного текста в hex (32 символа).
/// Эквивалент Python: hashlib.md5(normalized.encode()).hexdigest()
#[inline]
fn text_hash(text: &str) -> String {
    let normalized = normalize(text);
    let digest = md5::compute(normalized.as_bytes());
    hex_string(digest.as_ref())
}

/// Нормализует текст и возвращает его MD5-хэш в hex.
/// Используется в embedding_optimizer и semantic_cache для ключей кэша.
#[inline]
#[pyfunction]
fn normalize_and_hash(text: &str) -> String {
    text_hash(text)
}

/// Нормализует текст (без хэша). Для совместимости с Python _normalize_text.
#[inline]
#[pyfunction]
fn normalize_text(text: &str) -> String {
    normalize(text)
}

/// Батч: нормализация и MD5 для списка текстов.
/// Меньше переходов Python↔Rust при массовой обработке (embedding_optimizer, semantic_cache).
#[pyfunction]
fn normalize_and_hash_batch(texts: Vec<String>) -> Vec<String> {
    let mut out = Vec::with_capacity(texts.len());
    for s in &texts {
        out.push(text_hash(s.as_str()));
    }
    out
}

/// Модуль Python: cache_normalizer
#[pymodule]
fn cache_normalizer(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(normalize_and_hash, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_text, m)?)?;
    m.add_function(wrap_pyfunction!(normalize_and_hash_batch, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_normalize_empty() {
        assert_eq!(normalize(""), "");
        assert_eq!(normalize("   "), "");
    }

    #[test]
    fn test_normalize_spaces() {
        assert_eq!(normalize("  Hello   World  "), "hello world");
        assert_eq!(normalize("a b c"), "a b c");
    }

    #[test]
    fn test_normalize_lowercase() {
        assert_eq!(normalize("HELLO"), "hello");
    }

    #[test]
    fn test_text_hash_consistent() {
        let h1 = text_hash("  Hello   World  ");
        let h2 = text_hash("hello world");
        assert_eq!(h1, h2, "same normalized text must yield same MD5");
        assert_eq!(h1.len(), 32);
        assert!(h1.chars().all(|c| c.is_ascii_hexdigit()));
    }

    #[test]
    fn test_text_hash_empty() {
        let h = text_hash("");
        assert_eq!(h.len(), 32);
        // MD5 of empty string (Python: hashlib.md5(b'').hexdigest() = d41d8cd98f00b204e9800998ecf8427e)
        assert_eq!(h, "d41d8cd98f00b204e9800998ecf8427e");
    }

    #[test]
    fn test_normalize_and_hash_batch() {
        let texts = vec![
            String::from("  Hello   World  "),
            String::from(""),
            String::from("test"),
        ];
        let hashes = texts.iter().map(|s| text_hash(s)).collect::<Vec<_>>();
        assert_eq!(hashes.len(), 3);
        assert_eq!(hashes[0], text_hash("hello world"));
        assert_eq!(hashes[1], "d41d8cd98f00b204e9800998ecf8427e");
        assert_eq!(hashes[2], text_hash("test"));
    }
}

use sha2::{Digest, Sha256};

pub fn hash_norm(norm: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(norm.as_bytes());
    let result = hasher.finalize();
    hex::encode(result)
}

use rand::Rng;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumCandidate {
    pub id: String,
    pub score: f32,
    pub energy: f32, // Инвертированная релевантность (чем меньше, тем лучше)
}

pub struct QuantumInspiredOptimizer {
    pub temperature: f32,
    pub cooling_rate: f32,
}

impl QuantumInspiredOptimizer {
    pub fn new(temp: f32, cooling: f32) -> Self {
        Self {
            temperature: temp,
            cooling_rate: cooling,
        }
    }

    /// Алгоритм имитации отжига (Simulated Annealing) для поиска оптимального набора знаний или плана.
    /// Позволяет "туннелировать" через локальные минимумы.
    pub fn optimize<T: Clone>(
        &self,
        candidates: Vec<T>,
        energy_fn: impl Fn(&T) -> f32,
        iterations: usize,
    ) -> Vec<T> {
        let mut current_temp = self.temperature;
        let mut rng = rand::thread_rng();

        // В квантовом подходе мы выбираем не один лучший, а взвешенное состояние
        let mut results = candidates.clone();

        for _ in 0..iterations {
            if current_temp <= 0.1 {
                break;
            }

            for i in 0..results.len() {
                let j = rng.gen_range(0..results.len());

                let energy_i = energy_fn(&results[i]);
                let energy_j = energy_fn(&results[j]);

                // Если новое состояние лучше (энергия меньше) или по вероятности Больцмана
                if energy_j < energy_i
                    || rng.gen_bool(f64::from((-(energy_j - energy_i) / current_temp).exp()))
                {
                    results.swap(i, j);
                }
            }

            current_temp *= self.cooling_rate;
        }

        results
    }

    /// Вероятностный выбор (Quantum Sampling) на основе амплитуд.
    pub fn quantum_sample<T: Clone>(
        &self,
        candidates: Vec<T>,
        score_fn: impl Fn(&T) -> f32,
        limit: usize,
    ) -> Vec<T> {
        if candidates.is_empty() {
            return Vec::new();
        }

        let mut rng = rand::thread_rng();
        let mut sampled = Vec::new();
        let mut pool = candidates.clone();

        for _ in 0..limit {
            if pool.is_empty() {
                break;
            }

            let scores: Vec<f32> = pool
                .iter()
                .map(|c| score_fn(c).exp().max(f32::EPSILON))
                .collect();
            let total_score: f32 = scores.iter().sum();

            if total_score <= f32::EPSILON || !total_score.is_finite() {
                // Fallback: uniform random pick
                let idx = rng.gen_range(0..pool.len());
                sampled.push(pool.remove(idx));
                continue;
            }

            let mut pick = rng.gen_range(0.0_f32..total_score);
            let pool_len = pool.len();
            for (i, weight) in scores.iter().copied().enumerate().take(pool_len) {
                if pick <= weight || i == pool.len() - 1 {
                    sampled.push(pool.remove(i));
                    break;
                }
                pick -= weight;
            }
        }

        sampled
    }
}

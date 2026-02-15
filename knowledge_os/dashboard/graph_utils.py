import numpy as np

def optimized_force_layout(adjacency_matrix, node_degrees, iterations=100, 
                          initial_k=None, cooling_rate=0.95):
    """
    Оптимизированный Force-Directed Layout без scipy.
    Решает проблемы "бублика" и "прямоугольника" через нормализацию.
    """
    n = len(node_degrees)
    if n == 0:
        return np.zeros((0, 2))
    
    # Инициализация: случайное распределение по всему холсту
    pos = np.random.uniform(0.1, 0.9, (n, 2))
    
    if initial_k is None:
        # Увеличиваем k для создания больших пустот между узлами
        area = 10.0 
        initial_k = np.sqrt(area / n)
    
    k = initial_k
    temperature = 1.0
    
    # Предвычисляем индексы рёбер
    edges = np.column_stack(np.where(adjacency_matrix > 0))
    
    for iteration in range(iterations):
        forces = np.zeros((n, 2))
        
        # Отталкивание: используем экспоненциальное затухание для предотвращения слипания
        for i in range(n):
            diff = pos[i] - pos
            dist_sq = np.sum(diff**2, axis=1) + 1e-9
            dist = np.sqrt(dist_sq)
            
            # Сила отталкивания: k^2 / dist + дополнительный барьер на малых расстояниях
            f = (k * k) / dist + (0.01 / (dist**2))
            forces[i] += np.sum((diff.T * (f / dist)).T, axis=0)
        
        # ГРАВИТАЦИЯ: ПОЛНОСТЬЮ ОТКЛЮЧАЕМ (0.0)
        # Вместо нее используем мягкое ограничение границ в конце итерации
        gravity = 0.0 
        
        # Притяжение по рёбрам: делаем его ЛИНЕЙНЫМ, а не квадратичным
        # Это предотвращает стягивание в "кучу" при сильных связях
        if len(edges) > 0:
            for edge in edges:
                u, v = edge[0], edge[1]
                diff = pos[u] - pos[v]
                dist = np.sqrt(np.sum(diff**2)) + 1e-9
                
                # Линейная сила: F = dist / k (вместо dist^2 / k)
                f = dist / k 
                force_vec = (diff / dist) * f
                
                forces[u] -= force_vec
                forces[v] += force_vec
        
        # Адаптивный шаг
        step_size = 0.01 * temperature
        pos += forces * step_size
        
        # Жесткое ограничение границ вместо гравитации
        pos = np.clip(pos, -1.0, 1.0)
        
        # Центрирование
        pos -= pos.mean(axis=0)
        
        # Охлаждение
        temperature *= cooling_rate
        
        # Обновление с охлаждением
        step_size = 0.02 * temperature
        pos += forces * step_size
        
        # Нормализация (решает проблему "прямоугольника")
        pos -= pos.mean(axis=0)
        max_dist = np.max(np.abs(pos))
        if max_dist > 1e-6:
            pos = pos / max_dist * 0.9
        
        if iteration % 10 == 0:
            temperature *= cooling_rate
            k *= cooling_rate
    
    return pos

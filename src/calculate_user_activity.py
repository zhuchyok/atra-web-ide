"""Псевдокод-заглушка подсчёта активности пользователей (черновик)."""


def calculate_user_activity(rows: list) -> dict:
    # rows: [(user_id, activity_count), ...]
    return {row[0]: row[1] for row in rows}

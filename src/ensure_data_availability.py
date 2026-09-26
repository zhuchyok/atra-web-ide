def ensure_data_availability():
    if not data_exists():
        trigger_scout_for_data()
    else:
        proceed_with_data_analysis()
init:
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r requirements.txt

db:
	. .venv/bin/activate && python init_db.py

fees:
	. .venv/bin/activate && python set_fees.py

run:
	. .venv/bin/activate && python main.py

migrate:
	. .venv/bin/activate && python migrate_db.py

test-bitget-stop:
	. .venv/bin/activate && python scripts/test_bitget_stop_orders.py

# Test commands (через Rust с 14 потоками)
test:
	. .venv/bin/activate && python scripts/run_tests_rust.py --threads 14

test-unit:
	. .venv/bin/activate && python scripts/run_tests_rust.py --unit --threads 14

test-integration:
	. .venv/bin/activate && python scripts/run_tests_rust.py --integration --threads 14

# Backtest commands (через Rust с 14 потоками)
backtest:
	. .venv/bin/activate && python scripts/run_backtests_rust.py --threads 14

backtest-scripts:
	. .venv/bin/activate && python scripts/run_backtests_rust.py --scripts --threads 14

backtest-backtests:
	. .venv/bin/activate && python scripts/run_backtests_rust.py --backtests --threads 14

# Build Rust module
build-rust:
	cd rust-atra && RUSTFLAGS="-C target-cpu=native" cargo build --release

# Build Rust module with PGO (Profile-Guided Optimization)
build-rust-pgo:
	./scripts/build_rust_pgo.sh

# Install Rust module
install-rust: build-rust
	cd rust-atra && pip install -e .

all: init db fees run 
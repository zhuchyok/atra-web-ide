---
name: test-automation
description: Полная автоматизация тестирования - unit, integration, E2E. Генерация, выполнение и анализ тестов.
---

# Test Automation Skill

## Когда использовать
- Генерация тестов для нового кода
- Unit tests
- Integration tests
- E2E tests с Playwright
- Тестовый coverage analysis

## Test Types

### 1. Unit Tests
```python
def test_user_creation():
    user = User(name="John", email="john@test.com")
    assert user.name == "John"
    assert user.email == "john@test.com"
```

### 2. Integration Tests
```python
@pytest.mark.asyncio
async def test_user_repository():
    repo = UserRepository(db)
    user = await repo.create({"name": "John"})
    found = await repo.get(user.id)
    assert found.name == "John"
```

### 3. E2E Tests (Playwright)
```python
def test_login_flow():
    page.goto("/login")
    page.fill("#email", "test@test.com")
    page.fill("#password", "password")
    page.click("button[type=submit]")
    expect(page).to_have_url("/dashboard")
```

## Test Generation Patterns

### From Code
```python
# Generate tests for function
def generate_tests(function_code):
    # Extract inputs/outputs
    inputs = extract_parameters(function_code)
    outputs = extract_return(function_code)
    
    # Generate test cases
    tests = []
    for inputs in edge_cases:
        tests.append(make_test(inputs, outputs))
    
    return tests
```

### Property-Based Testing
```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_list(lst):
    result = sorted(lst)
    assert result == sorted(result)  # Property: sorted must be sorted
```

## Coverage

### Coverage Analysis
```bash
# Run with coverage
pytest --cov=src --cov-report=html

# Coverage report
Coverage.py report
```

### Target Coverage
- Unit tests: 80%+
- Integration: 60%+
- Critical paths: 100%

## Test Fixtures

### Fixtures Pattern
```python
@pytest.fixture
async def db():
    """Database fixture"""
    connection = await create_test_db()
    yield connection
    await connection.cleanup()

@pytest.fixture
def user():
    """User fixture"""
    return User(name="Test", email="test@test.com")
```

## Mock Patterns

### Unit Mocks
```python
from unittest.mock import Mock, patch

@patch('module.ClassName.method')
def test_with_mock(mock_method):
    mock_method.return_value = "mocked"
    result = call_function()
    assert result == "mocked"
```

### Async Mocks
```python
@pytest.mark.asyncio
async def test_async_mock():
    with patch('module.async_function', new_callable=AsyncMock) as mock:
        mock.return_value = "result"
        result = await call_async_function()
        assert result == "result"
```

## Commands
```bash
/test generate <file>     # Generate tests
/test run                # Run all tests
/test coverage          # Coverage report
/test watch             # Watch mode
/test ci                # CI mode
```

## Output
```json
{
  "tests_generated": 15,
  "tests_passed": 14,
  "tests_failed": 1,
  "coverage": {
    "line": 82,
    "branch": 75,
    "function": 90
  }
}
```
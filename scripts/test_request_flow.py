#!/usr/bin/env python3
"""
Диагностический скрипт для тестирования полного потока запроса к Victoria.
Проверяет каждый этап от отправки до получения ответа от модели.

Использование:
    python3 scripts/test_request_flow.py
    python3 scripts/test_request_flow.py --verbose
    python3 scripts/test_request_flow.py --model phi3.5:3.8b
"""

import argparse
import asyncio
import aiohttp
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

# Colors for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def log(msg: str, color: str = "", prefix: str = ""):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"{Colors.CYAN}[{timestamp}]{Colors.END} {prefix}{color}{msg}{Colors.END}")

def log_success(msg: str):
    log(msg, Colors.GREEN, "✅ ")

def log_error(msg: str):
    log(msg, Colors.RED, "❌ ")

def log_warning(msg: str):
    log(msg, Colors.YELLOW, "⚠️ ")

def log_info(msg: str):
    log(msg, Colors.BLUE, "ℹ️ ")

def log_step(msg: str):
    log(msg, Colors.BOLD, ">>> ")


class RequestFlowTester:
    """Tests the full request flow from client to model"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.victoria_url = os.getenv("VICTORIA_URL", "http://localhost:8010")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.mlx_url = os.getenv("MLX_URL", "http://localhost:11435")
        self.results: Dict[str, Any] = {}
        
    async def test_connectivity(self) -> Dict[str, bool]:
        """Test connectivity to all services"""
        log_step("STEP 1: Testing Service Connectivity")
        
        services = {
            "Victoria": f"{self.victoria_url}/health",
            "Ollama": f"{self.ollama_url}/api/tags",
            "MLX": f"{self.mlx_url}/api/tags",
        }
        
        results = {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            for name, url in services.items():
                try:
                    start = time.time()
                    async with session.get(url) as response:
                        elapsed = (time.time() - start) * 1000
                        if response.status == 200:
                            results[name] = True
                            log_success(f"{name}: OK ({elapsed:.0f}ms) - {url}")
                            
                            # Show model count for LLM services
                            if name in ("Ollama", "MLX"):
                                data = await response.json()
                                models = data.get("models", [])
                                log_info(f"  Available models: {len(models)}")
                                if self.verbose and models:
                                    for m in models[:5]:
                                        log_info(f"    - {m.get('name', 'unknown')}")
                                    if len(models) > 5:
                                        log_info(f"    ... and {len(models) - 5} more")
                        else:
                            results[name] = False
                            log_error(f"{name}: HTTP {response.status} - {url}")
                except Exception as e:
                    results[name] = False
                    log_error(f"{name}: Connection failed - {e}")
        
        self.results["connectivity"] = results
        return results
    
    async def get_available_models(self) -> Dict[str, List[str]]:
        """Get list of available models from Ollama and MLX"""
        log_step("STEP 2: Getting Available Models")
        
        models = {"ollama": [], "mlx": []}
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            # Ollama
            try:
                async with session.get(f"{self.ollama_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models["ollama"] = [m.get("name", "") for m in data.get("models", [])]
                        log_success(f"Ollama models: {len(models['ollama'])}")
            except Exception as e:
                log_warning(f"Could not get Ollama models: {e}")
            
            # MLX
            try:
                async with session.get(f"{self.mlx_url}/api/tags") as response:
                    if response.status == 200:
                        data = await response.json()
                        models["mlx"] = [m.get("name", "") for m in data.get("models", [])]
                        log_success(f"MLX models: {len(models['mlx'])}")
            except Exception as e:
                log_warning(f"Could not get MLX models: {e}")
        
        self.results["models"] = models
        return models
    
    async def test_model_directly(self, model: str, use_mlx: bool = False) -> Dict[str, Any]:
        """Test a model directly without going through Victoria"""
        base_url = self.mlx_url if use_mlx else self.ollama_url
        source = "MLX" if use_mlx else "Ollama"
        
        log_step(f"STEP 3: Testing Model Directly ({source})")
        log_info(f"Model: {model}")
        log_info(f"URL: {base_url}/api/chat")
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Respond briefly."},
                {"role": "user", "content": "Say hello in exactly 3 words."}
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }
        
        result = {
            "model": model,
            "source": source,
            "success": False,
            "response": None,
            "error": None,
            "elapsed_ms": 0
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
            try:
                start = time.time()
                log_info(f"Sending request...")
                
                async with session.post(f"{base_url}/api/chat", json=payload) as response:
                    elapsed = (time.time() - start) * 1000
                    result["elapsed_ms"] = elapsed
                    
                    log_info(f"HTTP Status: {response.status}, Time: {elapsed:.0f}ms")
                    
                    if response.status == 200:
                        data = await response.json()
                        content = data.get("message", {}).get("content", "")
                        result["success"] = True
                        result["response"] = content
                        log_success(f"Model response: {content[:200]}...")
                    else:
                        error_body = await response.text()
                        result["error"] = error_body[:500]
                        log_error(f"Model error: {error_body[:300]}")
                        
                        # Check for crash indicators
                        crash_indicators = ["unexpectedly stopped", "resource limitations", "out of memory"]
                        if any(ind in error_body.lower() for ind in crash_indicators):
                            log_warning("⚠️ MODEL CRASH DETECTED - This model requires more resources!")
                            
            except asyncio.TimeoutError:
                result["error"] = "Timeout (120s)"
                log_error("Request timed out after 120 seconds")
            except Exception as e:
                result["error"] = str(e)
                log_error(f"Exception: {type(e).__name__}: {e}")
        
        self.results["direct_model_test"] = result
        return result
    
    async def test_victoria_request(self, goal: str = "скажи привет") -> Dict[str, Any]:
        """Test a full request through Victoria"""
        log_step("STEP 4: Testing Full Victoria Request Flow")
        
        log_info(f"Goal: {goal}")
        log_info(f"URL: {self.victoria_url}/run")
        
        payload = {
            "goal": goal,
            "max_steps": 3,
            "project_context": "atra-web-ide"
        }
        
        result = {
            "success": False,
            "response": None,
            "error": None,
            "correlation_id": None,
            "task_id": None,
            "elapsed_ms": 0,
            "model_used": None
        }
        
        # Use async mode for more detailed tracking
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=300)) as session:
            try:
                start = time.time()
                log_info("Sending async request to Victoria...")
                
                async with session.post(
                    f"{self.victoria_url}/run",
                    json=payload,
                    params={"async_mode": "true"}
                ) as response:
                    first_response_time = (time.time() - start) * 1000
                    log_info(f"Initial response: HTTP {response.status}, Time: {first_response_time:.0f}ms")
                    
                    if response.status == 202:
                        data = await response.json()
                        result["task_id"] = data.get("task_id")
                        result["correlation_id"] = data.get("correlation_id")
                        
                        log_success(f"Task accepted!")
                        log_info(f"  Task ID: {result['task_id']}")
                        log_info(f"  Correlation ID: {result['correlation_id']}")
                        
                        # Poll for result
                        task_id = result["task_id"]
                        poll_start = time.time()
                        max_wait = 300  # 5 minutes
                        
                        while (time.time() - poll_start) < max_wait:
                            await asyncio.sleep(2)
                            
                            async with session.get(f"{self.victoria_url}/run/status/{task_id}") as status_response:
                                if status_response.status == 200:
                                    status_data = await status_response.json()
                                    status = status_data.get("status", "")
                                    
                                    log_info(f"  Polling... Status: {status}")
                                    
                                    if status == "completed":
                                        elapsed = (time.time() - start) * 1000
                                        result["elapsed_ms"] = elapsed
                                        result["success"] = True
                                        result["response"] = status_data.get("output", "")
                                        
                                        # Extract model info from knowledge
                                        knowledge = status_data.get("knowledge", {})
                                        metadata = knowledge.get("metadata", {})
                                        result["model_used"] = metadata.get("model_used") or metadata.get("model")
                                        
                                        log_success(f"Task completed! Total time: {elapsed:.0f}ms")
                                        log_info(f"  Model used: {result['model_used']}")
                                        log_info(f"  Response preview: {result['response'][:200]}...")
                                        break
                                        
                                    elif status == "failed":
                                        result["error"] = status_data.get("error", "Unknown error")
                                        log_error(f"Task failed: {result['error']}")
                                        break
                                else:
                                    log_warning(f"  Status check returned HTTP {status_response.status}")
                        else:
                            result["error"] = "Polling timeout (5 minutes)"
                            log_error("Task did not complete within 5 minutes")
                            
                    elif response.status == 200:
                        # Sync response
                        data = await response.json()
                        elapsed = (time.time() - start) * 1000
                        result["elapsed_ms"] = elapsed
                        result["success"] = data.get("status") == "success"
                        result["response"] = data.get("output", "")
                        result["correlation_id"] = data.get("correlation_id")
                        
                        knowledge = data.get("knowledge", {})
                        metadata = knowledge.get("metadata", {})
                        result["model_used"] = metadata.get("model_used") or metadata.get("model")
                        
                        if result["success"]:
                            log_success(f"Request completed! Time: {elapsed:.0f}ms")
                        else:
                            result["error"] = data.get("error", "Unknown error")
                            log_error(f"Request failed: {result['error']}")
                    else:
                        error_body = await response.text()
                        result["error"] = f"HTTP {response.status}: {error_body[:200]}"
                        log_error(f"Request failed: {result['error']}")
                        
            except asyncio.TimeoutError:
                result["error"] = "Request timeout (5 minutes)"
                log_error("Request timed out")
            except Exception as e:
                result["error"] = str(e)
                log_error(f"Exception: {type(e).__name__}: {e}")
        
        self.results["victoria_request"] = result
        return result
    
    def print_summary(self):
        """Print a summary of all test results"""
        print()
        print("=" * 60)
        print(f"{Colors.BOLD}📊 TEST SUMMARY{Colors.END}")
        print("=" * 60)
        
        # Connectivity
        conn = self.results.get("connectivity", {})
        print(f"\n{Colors.BOLD}Service Connectivity:{Colors.END}")
        for service, ok in conn.items():
            status = f"{Colors.GREEN}✅ OK{Colors.END}" if ok else f"{Colors.RED}❌ FAILED{Colors.END}"
            print(f"  {service}: {status}")
        
        # Models
        models = self.results.get("models", {})
        if models:
            print(f"\n{Colors.BOLD}Available Models:{Colors.END}")
            print(f"  Ollama: {len(models.get('ollama', []))} models")
            print(f"  MLX: {len(models.get('mlx', []))} models")
        
        # Direct model test
        direct = self.results.get("direct_model_test", {})
        if direct:
            print(f"\n{Colors.BOLD}Direct Model Test ({direct.get('source', 'unknown')}):{Colors.END}")
            print(f"  Model: {direct.get('model', 'unknown')}")
            if direct.get("success"):
                print(f"  Status: {Colors.GREEN}✅ SUCCESS{Colors.END}")
                print(f"  Time: {direct.get('elapsed_ms', 0):.0f}ms")
            else:
                print(f"  Status: {Colors.RED}❌ FAILED{Colors.END}")
                print(f"  Error: {direct.get('error', 'unknown')[:100]}")
        
        # Victoria request
        victoria = self.results.get("victoria_request", {})
        if victoria:
            print(f"\n{Colors.BOLD}Victoria Request Flow:{Colors.END}")
            if victoria.get("success"):
                print(f"  Status: {Colors.GREEN}✅ SUCCESS{Colors.END}")
                print(f"  Time: {victoria.get('elapsed_ms', 0):.0f}ms")
                print(f"  Model: {victoria.get('model_used', 'unknown')}")
                print(f"  Correlation ID: {victoria.get('correlation_id', 'unknown')[:20]}...")
            else:
                print(f"  Status: {Colors.RED}❌ FAILED{Colors.END}")
                print(f"  Error: {victoria.get('error', 'unknown')[:100]}")
        
        print()
        print("=" * 60)
        
        # Overall status
        all_ok = (
            all(conn.values()) and
            direct.get("success", False) and
            victoria.get("success", False)
        )
        
        if all_ok:
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED!{Colors.END}")
        else:
            print(f"{Colors.RED}{Colors.BOLD}⚠️ SOME TESTS FAILED - See details above{Colors.END}")
        
        print("=" * 60)


async def main():
    parser = argparse.ArgumentParser(description='Test Victoria request flow')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--model', default='phi3.5:3.8b', help='Model to test directly')
    parser.add_argument('--use-mlx', action='store_true', help='Use MLX instead of Ollama for direct test')
    parser.add_argument('--goal', default='скажи привет', help='Goal for Victoria request')
    parser.add_argument('--skip-direct', action='store_true', help='Skip direct model test')
    parser.add_argument('--skip-victoria', action='store_true', help='Skip Victoria request test')
    args = parser.parse_args()
    
    print()
    print("=" * 60)
    print(f"{Colors.BOLD}🔍 VICTORIA REQUEST FLOW DIAGNOSTIC{Colors.END}")
    print(f"   Testing full request path from client to model")
    print("=" * 60)
    print()
    
    tester = RequestFlowTester(verbose=args.verbose)
    
    # Step 1: Test connectivity
    await tester.test_connectivity()
    print()
    
    # Step 2: Get available models
    await tester.get_available_models()
    print()
    
    # Step 3: Test model directly (optional)
    if not args.skip_direct:
        await tester.test_model_directly(args.model, use_mlx=args.use_mlx)
        print()
    
    # Step 4: Test Victoria request (optional)
    if not args.skip_victoria:
        await tester.test_victoria_request(args.goal)
        print()
    
    # Summary
    tester.print_summary()


if __name__ == "__main__":
    asyncio.run(main())

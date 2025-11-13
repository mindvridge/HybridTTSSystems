"""
Banking Balance Inquiry POC (Proof of Concept)
Demonstrates hybrid TTS system for banking domain

This POC shows:
1. Template-based responses for common queries
2. Cache hit rate optimization
3. Cost savings estimation
4. Real-world banking scenarios
"""
import asyncio
import random
from datetime import datetime
from typing import List, Dict
import httpx


class BankingPOC:
    """Banking Balance Inquiry POC Simulator"""

    def __init__(self, api_base_url: str = "http://localhost:8000/api/v1"):
        self.api_base_url = api_base_url
        self.client = httpx.AsyncClient()

        # Sample customer data
        self.customers = [
            {"name": "김철수", "account": "1234-5678", "balance": 1250000},
            {"name": "이영희", "account": "2345-6789", "balance": 850000},
            {"name": "박민수", "account": "3456-7890", "balance": 3200000},
            {"name": "정수진", "account": "4567-8901", "balance": 450000},
            {"name": "최동욱", "account": "5678-9012", "balance": 1800000},
        ]

        # Common query patterns (Pareto principle: 20% of phrases = 80% of usage)
        self.common_queries = [
            "잔액 조회해주세요",
            "현재 잔액이 얼마인가요",
            "계좌 잔액 알려주세요",
            "내 계좌에 얼마 있어요",
            "잔액 확인",
        ]

        # Less common queries
        self.uncommon_queries = [
            "제 통장에 돈이 얼마나 남아있나요",
            "계좌 잔고 좀 알려주실래요",
            "잔액이 궁금합니다",
            "얼마 있는지 확인해주세요",
        ]

    async def simulate_balance_inquiry(
        self, customer: Dict, query: str
    ) -> Dict:
        """Simulate a single balance inquiry"""
        try:
            # Use template-based synthesis
            response = await self.client.post(
                f"{self.api_base_url}/synthesize/template",
                params={
                    "template_id": "balance_inquiry_result",
                    "voice": "ko-KR-Neural2-A",
                },
                json={
                    "customer_name": customer["name"],
                    "balance": f"{customer['balance']:,}",
                },
            )

            headers = response.headers
            return {
                "customer": customer["name"],
                "query": query,
                "status": "success",
                "cache_status": headers.get("X-Cache-Status", "UNKNOWN"),
                "method": headers.get("X-Method", "UNKNOWN"),
                "latency_ms": float(headers.get("X-Latency-Ms", 0)),
                "audio_size": len(response.content),
            }

        except Exception as e:
            return {
                "customer": customer["name"],
                "query": query,
                "status": "error",
                "error": str(e),
            }

    async def run_scenario(
        self, num_requests: int = 100, common_ratio: float = 0.8
    ):
        """
        Run POC scenario with specified number of requests

        Args:
            num_requests: Total number of requests to simulate
            common_ratio: Ratio of common queries (default 0.8 for Pareto principle)
        """
        print("\n" + "=" * 80)
        print("Banking Balance Inquiry POC - Hybrid TTS System")
        print("=" * 80)
        print(f"\nSimulating {num_requests} balance inquiries...")
        print(f"Common query ratio: {common_ratio * 100}%\n")

        results = []

        for i in range(num_requests):
            # Select customer randomly
            customer = random.choice(self.customers)

            # Select query based on common ratio (Pareto principle)
            if random.random() < common_ratio:
                query = random.choice(self.common_queries)
            else:
                query = random.choice(self.uncommon_queries)

            result = await self.simulate_balance_inquiry(customer, query)
            results.append(result)

            if (i + 1) % 10 == 0:
                print(f"Progress: {i + 1}/{num_requests} requests completed")

        # Analyze results
        self.analyze_results(results)

        return results

    def analyze_results(self, results: List[Dict]):
        """Analyze POC results and display statistics"""
        successful = [r for r in results if r["status"] == "success"]

        if not successful:
            print("\nNo successful requests to analyze")
            return

        # Calculate statistics
        cache_hits = len([r for r in successful if r["cache_status"] == "HIT"])
        cache_misses = len([r for r in successful if r["cache_status"] == "MISS"])
        total = len(successful)

        cache_hit_rate = cache_hits / total if total > 0 else 0

        # Latency statistics
        latencies = [r["latency_ms"] for r in successful]
        avg_latency = sum(latencies) / len(latencies)
        min_latency = min(latencies)
        max_latency = max(latencies)

        # Method distribution
        methods = {}
        for r in successful:
            method = r.get("method", "UNKNOWN")
            methods[method] = methods.get(method, 0) + 1

        # Cost savings estimation
        # Assume: TTS API costs $16 per 1M characters (Neural voice)
        # Average query response: ~50 characters
        # Cost per TTS synthesis: ~$0.0008
        # Cache hit costs: ~$0.00001 (storage/retrieval)
        tts_cost_per_request = 0.0008
        cache_cost_per_request = 0.00001

        cost_without_cache = total * tts_cost_per_request
        actual_cost = (
            cache_hits * cache_cost_per_request + cache_misses * tts_cost_per_request
        )
        cost_savings = cost_without_cache - actual_cost
        cost_reduction_rate = cost_savings / cost_without_cache if cost_without_cache > 0 else 0

        # Display results
        print("\n" + "=" * 80)
        print("POC RESULTS")
        print("=" * 80)

        print(f"\nTotal Requests: {total}")
        print(f"Cache Hits: {cache_hits}")
        print(f"Cache Misses: {cache_misses}")
        print(f"Cache Hit Rate: {cache_hit_rate * 100:.2f}%")

        print("\nLatency Statistics:")
        print(f"  Average: {avg_latency:.2f} ms")
        print(f"  Min: {min_latency:.2f} ms")
        print(f"  Max: {max_latency:.2f} ms")

        print("\nMethod Distribution:")
        for method, count in sorted(methods.items(), key=lambda x: x[1], reverse=True):
            print(f"  {method}: {count} ({count / total * 100:.1f}%)")

        print("\nCost Analysis:")
        print(f"  Cost without cache: ${cost_without_cache:.4f}")
        print(f"  Actual cost with cache: ${actual_cost:.4f}")
        print(f"  Cost savings: ${cost_savings:.4f}")
        print(f"  Cost reduction rate: {cost_reduction_rate * 100:.2f}%")

        # Target achievement
        print("\nTarget Achievement:")
        target_hit_rate = 0.80
        target_cost_reduction = 0.70

        hit_rate_met = cache_hit_rate >= target_hit_rate
        cost_met = cost_reduction_rate >= target_cost_reduction

        print(
            f"  Cache Hit Rate Target (80%): {'✓ ACHIEVED' if hit_rate_met else '✗ NOT MET'} "
            f"({cache_hit_rate * 100:.1f}%)"
        )
        print(
            f"  Cost Reduction Target (70%): {'✓ ACHIEVED' if cost_met else '✗ NOT MET'} "
            f"({cost_reduction_rate * 100:.1f}%)"
        )

        if hit_rate_met and cost_met:
            print("\n🎉 POC SUCCESS! Both targets achieved!")
        else:
            print(
                "\n⚠️  Targets not fully met. Consider increasing common query ratio or cache warm-up."
            )

        print("=" * 80 + "\n")

    async def warm_up_cache(self):
        """
        Pre-warm cache with common phrases
        This simulates initial cache population
        """
        print("\nWarming up cache with common queries...")

        for customer in self.customers:
            for query in self.common_queries:
                await self.simulate_balance_inquiry(customer, query)

        print("Cache warm-up complete!\n")

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


async def main():
    """Main POC execution"""
    poc = BankingPOC()

    try:
        # Optional: Warm up cache first
        # await poc.warm_up_cache()

        # Run main scenario
        # 100 requests with 80% common queries (Pareto principle)
        await poc.run_scenario(num_requests=100, common_ratio=0.80)

    finally:
        await poc.close()


if __name__ == "__main__":
    print("\n📊 Banking Balance Inquiry POC")
    print("Ensure the API server is running at http://localhost:8000\n")

    asyncio.run(main())

"""
Performance Tester Module
Handles concurrent SAML assertion delivery to service providers
"""

import asyncio
import time
import statistics
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin
import aiohttp

from saml_builder import SAMLAssertionBuilder
from user_generator import TestUser, UserGenerator


@dataclass
class RequestResult:
    """Result of a single SAML assertion request"""
    user_id: str
    success: bool
    status_code: Optional[int] = None
    response_time_ms: float = 0.0
    error_message: Optional[str] = None
    response_body: Optional[str] = None
    response_headers: Optional[Dict[str, str]] = None


@dataclass
class TestResults:
    """Aggregated results from a performance test run"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_time_seconds: float = 0.0
    requests_per_second: float = 0.0
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    median_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    p99_response_time_ms: float = 0.0
    individual_results: List[RequestResult] = field(default_factory=list)
    error_summary: Dict[str, int] = field(default_factory=dict)

    def calculate_statistics(self):
        """Calculate statistics from individual results"""
        if not self.individual_results:
            return

        self.total_requests = len(self.individual_results)
        self.successful_requests = sum(1 for r in self.individual_results if r.success)
        self.failed_requests = self.total_requests - self.successful_requests

        if self.total_time_seconds > 0:
            self.requests_per_second = self.total_requests / self.total_time_seconds

        response_times = [r.response_time_ms for r in self.individual_results]
        if response_times:
            self.avg_response_time_ms = statistics.mean(response_times)
            self.min_response_time_ms = min(response_times)
            self.max_response_time_ms = max(response_times)
            self.median_response_time_ms = statistics.median(response_times)

            sorted_times = sorted(response_times)
            p95_idx = int(len(sorted_times) * 0.95)
            p99_idx = int(len(sorted_times) * 0.99)
            self.p95_response_time_ms = sorted_times[min(p95_idx, len(sorted_times) - 1)]
            self.p99_response_time_ms = sorted_times[min(p99_idx, len(sorted_times) - 1)]

        # Summarize errors
        for result in self.individual_results:
            if not result.success and result.error_message:
                error_key = result.error_message[:100]  # Truncate long errors
                self.error_summary[error_key] = self.error_summary.get(error_key, 0) + 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert results to dictionary"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": f"{(self.successful_requests / self.total_requests * 100):.2f}%" if self.total_requests > 0 else "0%",
            "total_time_seconds": round(self.total_time_seconds, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "response_times_ms": {
                "avg": round(self.avg_response_time_ms, 2),
                "min": round(self.min_response_time_ms, 2),
                "max": round(self.max_response_time_ms, 2),
                "median": round(self.median_response_time_ms, 2),
                "p95": round(self.p95_response_time_ms, 2),
                "p99": round(self.p99_response_time_ms, 2),
            },
            "error_summary": self.error_summary,
        }

    def print_summary(self):
        """Print a formatted summary of the results"""
        print("\n" + "=" * 60)
        print("SAML PERFORMANCE TEST RESULTS")
        print("=" * 60)
        print(f"\nTotal Requests:     {self.total_requests}")
        print(f"Successful:         {self.successful_requests}")
        print(f"Failed:             {self.failed_requests}")
        if self.total_requests > 0:
            print(f"Success Rate:       {(self.successful_requests / self.total_requests * 100):.2f}%")
        print(f"\nTotal Time:         {self.total_time_seconds:.2f} seconds")
        print(f"Requests/Second:    {self.requests_per_second:.2f}")
        print(f"\nResponse Times (ms):")
        print(f"  Average:          {self.avg_response_time_ms:.2f}")
        print(f"  Min:              {self.min_response_time_ms:.2f}")
        print(f"  Max:              {self.max_response_time_ms:.2f}")
        print(f"  Median:           {self.median_response_time_ms:.2f}")
        print(f"  95th Percentile:  {self.p95_response_time_ms:.2f}")
        print(f"  99th Percentile:  {self.p99_response_time_ms:.2f}")

        if self.error_summary:
            print(f"\nError Summary:")
            for error, count in sorted(self.error_summary.items(), key=lambda x: -x[1]):
                print(f"  [{count}x] {error}")

        print("=" * 60 + "\n")


class SAMLPerformanceTester:
    """Executes concurrent SAML assertion requests for performance testing"""

    def __init__(
        self,
        sp_url: str,
        saml_builder: SAMLAssertionBuilder,
        timeout_seconds: int = 30,
        verify_ssl: bool = True,
        debug: bool = False,
    ):
        """
        Initialize the performance tester

        Args:
            sp_url: Service Provider URL to send assertions to
            saml_builder: SAMLAssertionBuilder instance for creating assertions
            timeout_seconds: Request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
            debug: Whether to capture full response bodies and headers
        """
        self.sp_url = sp_url
        self.saml_builder = saml_builder
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.verify_ssl = verify_ssl
        self.debug = debug

    async def _send_assertion(
        self,
        session_pool: asyncio.Queue,
        user: TestUser,
    ) -> RequestResult:
        """
        Send a single SAML assertion.
        Acquires a session from the pool and returns it (with cleared cookies) when done.

        Args:
            session_pool: pool of reusable ClientSessions (size == concurrency)
            user: TestUser to create assertion for

        Returns:
            RequestResult with timing and status info
        """
        session = await session_pool.get()
        start_time = time.perf_counter()

        try:
            saml_response = self.saml_builder.build_signed_response(
                user_id=user.user_id,
                user_email=user.email,
                groups=user.groups,
                custom_attributes=user.custom_attributes,
            )

            data = {"SAMLResponse": saml_response}

            if user.custom_attributes.get("relay_state"):
                data["RelayState"] = user.custom_attributes["relay_state"]

            async with session.post(
                self.sp_url,
                data=data,
                allow_redirects=False,
            ) as response:
                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000

                response_body = await response.text()

                success = 200 <= response.status < 400

                response_headers = dict(response.headers) if self.debug else None
                body_to_store = response_body if self.debug else (response_body[:500] if response_body else None)

                return RequestResult(
                    user_id=user.user_id,
                    success=success,
                    status_code=response.status,
                    response_time_ms=response_time_ms,
                    response_body=body_to_store,
                    error_message=None if success else f"HTTP {response.status}",
                    response_headers=response_headers,
                )

        except asyncio.TimeoutError:
            end_time = time.perf_counter()
            return RequestResult(
                user_id=user.user_id,
                success=False,
                response_time_ms=(end_time - start_time) * 1000,
                error_message="Request timeout",
            )
        except aiohttp.ClientError as e:
            end_time = time.perf_counter()
            return RequestResult(
                user_id=user.user_id,
                success=False,
                response_time_ms=(end_time - start_time) * 1000,
                error_message=f"Client error: {str(e)}",
            )
        except Exception as e:
            end_time = time.perf_counter()
            return RequestResult(
                user_id=user.user_id,
                success=False,
                response_time_ms=(end_time - start_time) * 1000,
                error_message=f"Unexpected error: {str(e)}",
            )
        finally:
            session.cookie_jar.clear()
            await session_pool.put(session)

    async def run_test(
        self,
        users: List[TestUser],
        concurrency: int = 10,
        progress_callback=None,
    ) -> TestResults:
        """
        Run the performance test with the given users

        Args:
            users: List of TestUser instances to test with
            concurrency: Maximum number of concurrent requests
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            TestResults with aggregated statistics
        """
        results = TestResults()
        ssl_context = None if self.verify_ssl else False

        connector = aiohttp.TCPConnector(
            limit=concurrency,
            ssl=ssl_context,
        )

        # Fixed pool of `concurrency` sessions — reused across all users
        sessions = [
            aiohttp.ClientSession(
                timeout=self.timeout,
                connector=connector,
                connector_owner=False,
            )
            for _ in range(concurrency)
        ]

        _AFFINITY_NAMES = {"affinity", "awsalb", "awsalbcors", "jsessionid"}

        async def _warmup(session: aiohttp.ClientSession) -> None:
            async with session.get(self.sp_url, allow_redirects=True):
                pass

        await asyncio.gather(*(_warmup(s) for s in sessions))

        for i, session in enumerate(sessions):
            affinity = next(
                (f"{m.key}={m.value}" for m in session.cookie_jar if m.key.lower() in _AFFINITY_NAMES),
                "none",
            )
            print(f"[connection {i + 1:>4}] affinity={affinity}")

        session_pool: asyncio.Queue = asyncio.Queue()
        for session in sessions:
            await session_pool.put(session)

        start_time = time.perf_counter()

        try:
            tasks = [
                self._send_assertion(session_pool, user)
                for user in users
            ]

            completed = 0
            for coro in asyncio.as_completed(tasks):
                result = await coro
                results.individual_results.append(result)
                completed += 1

                if progress_callback:
                    progress_callback(completed, len(users))
        finally:
            for session in sessions:
                await session.close()
            await connector.close()

        end_time = time.perf_counter()
        results.total_time_seconds = end_time - start_time
        results.calculate_statistics()

        return results

    def run_test_sync(
        self,
        users: List[TestUser],
        concurrency: int = 10,
        progress_callback=None,
    ) -> TestResults:
        """
        Synchronous wrapper for run_test

        Args:
            users: List of TestUser instances
            concurrency: Maximum concurrent requests
            progress_callback: Optional progress callback

        Returns:
            TestResults
        """
        return asyncio.run(
            self.run_test(users, concurrency, progress_callback)
        )


async def run_performance_test(
    sp_url: str,
    issuer: str,
    private_key_path: str,
    certificate_path: str,
    num_users: int,
    concurrency: int,
    groups: List[str],
    custom_attributes: Optional[dict] = None,
    verify_ssl: bool = True,
    timeout_seconds: int = 30,
    verbose: bool = False,
    debug: bool = False,
) -> TestResults:
    """
    Convenience function to run a complete performance test

    Args:
        sp_url: Service Provider URL
        issuer: SAML Issuer ID
        private_key_path: Path to private key for signing
        certificate_path: Path to certificate
        num_users: Number of concurrent users to simulate
        concurrency: Maximum concurrent requests
        groups: List of groups to include in assertions
        custom_attributes: Optional custom attributes
        verify_ssl: Whether to verify SSL certificates
        timeout_seconds: Request timeout
        verbose: Whether to print progress
        debug: Whether to capture full response details

    Returns:
        TestResults with complete statistics
    """
    # Build the SAML assertion builder
    builder = SAMLAssertionBuilder(
        issuer=issuer,
        sp_url=sp_url,
        private_key_path=private_key_path,
        certificate_path=certificate_path,
    )

    # Generate test users
    generator = UserGenerator(default_groups=groups)
    users = generator.generate_users(
        count=num_users,
        custom_attributes=custom_attributes,
    )

    # Create tester
    tester = SAMLPerformanceTester(
        sp_url=sp_url,
        saml_builder=builder,
        timeout_seconds=timeout_seconds,
        verify_ssl=verify_ssl,
        debug=debug,
    )

    # Progress callback
    def progress(completed, total):
        if verbose and completed % 1000 == 0:
            print(f"Progress: {completed}/{total} ({completed/total*100:.1f}%)", flush=True)

    # Run the test
    results = await tester.run_test(
        users=users,
        concurrency=concurrency,
        progress_callback=progress if verbose else None,
    )

    if verbose:
        print()  # New line after progress

    return results

#!/usr/bin/env python3
"""
SAML Performance Test CLI
Command-line interface for running SAML assertion performance tests
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from typing import Optional, List

import click

from saml_builder import SAMLAssertionBuilder
from user_generator import UserGenerator, SequentialUserGenerator
from performance_tester import SAMLPerformanceTester, run_performance_test


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """SAML Performance Testing Tool

    Send multiple SAML assertions to a Service Provider for performance testing.
    Each assertion is signed and contains configurable user attributes and groups.
    """
    pass


@cli.command()
@click.option(
    "--sp-url",
    "-u",
    required=True,
    help="Service Provider URL to send SAML assertions to (e.g., https://example.com/saml/acs)",
)
@click.option(
    "--issuer",
    "-i",
    required=True,
    help="SAML Issuer ID (Identity Provider entity ID)",
)
@click.option(
    "--private-key",
    "-k",
    required=True,
    type=click.Path(exists=True),
    help="Path to PEM-encoded private key for signing assertions",
)
@click.option(
    "--certificate",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to PEM-encoded certificate for signing assertions",
)
@click.option(
    "--users",
    "-n",
    default=10,
    type=int,
    help="Number of users to simulate (default: 10)",
)
@click.option(
    "--concurrency",
    "-j",
    default=5,
    type=int,
    help="Maximum concurrent requests (default: 5)",
)
@click.option(
    "--groups",
    "-g",
    multiple=True,
    help="Group names to include in assertions (can be specified multiple times)",
)
@click.option(
    "--attribute",
    "-a",
    multiple=True,
    type=(str, str),
    help="Custom attribute as name=value pair (can be specified multiple times)",
)
@click.option(
    "--timeout",
    "-t",
    default=30,
    type=int,
    help="Request timeout in seconds (default: 30)",
)
@click.option(
    "--no-verify-ssl",
    is_flag=True,
    default=False,
    help="Disable SSL certificate verification",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file for JSON results",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show progress and detailed output",
)
@click.option(
    "--quiet",
    "-q",
    is_flag=True,
    default=False,
    help="Suppress all output except errors",
)
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    default=False,
    help="Show detailed server responses for each request",
)
def test(
    sp_url: str,
    issuer: str,
    private_key: str,
    certificate: str,
    users: int,
    concurrency: int,
    groups: tuple,
    attribute: tuple,
    timeout: int,
    no_verify_ssl: bool,
    output: Optional[str],
    verbose: bool,
    quiet: bool,
    debug: bool,
):
    """Run a SAML performance test.

    Sends multiple SAML assertions to the specified Service Provider URL,
    each with a different user identity. Measures response times and success rates.

    Example:
        saml-perf test -u https://sp.example.com/saml/acs -i https://idp.example.com \\
            -k private.key -c certificate.pem -n 100 -j 10 -g admins -g users
    """
    if quiet and verbose:
        raise click.UsageError("Cannot use both --quiet and --verbose")

    if quiet and debug:
        raise click.UsageError("Cannot use both --quiet and --debug")

    # Convert attributes to dict
    custom_attributes = {}
    for name, value in attribute:
        if name in custom_attributes:
            if isinstance(custom_attributes[name], list):
                custom_attributes[name].append(value)
            else:
                custom_attributes[name] = [custom_attributes[name], value]
        else:
            custom_attributes[name] = value

    groups_list = list(groups) if groups else []

    if not quiet:
        click.echo(f"SAML Performance Test")
        click.echo(f"=" * 50)
        click.echo(f"Target SP URL:    {sp_url}")
        click.echo(f"Issuer:           {issuer}")
        click.echo(f"Users:            {users}")
        click.echo(f"Concurrency:      {concurrency}")
        click.echo(f"Groups:           {', '.join(groups_list) if groups_list else '(none)'}")
        click.echo(f"Timeout:          {timeout}s")
        click.echo(f"SSL Verification: {'disabled' if no_verify_ssl else 'enabled'}")
        click.echo(f"=" * 50)
        click.echo()

    try:
        results = asyncio.run(
            run_performance_test(
                sp_url=sp_url,
                issuer=issuer,
                private_key_path=private_key,
                certificate_path=certificate,
                num_users=users,
                concurrency=concurrency,
                groups=groups_list,
                custom_attributes=custom_attributes if custom_attributes else None,
                verify_ssl=not no_verify_ssl,
                timeout_seconds=timeout,
                verbose=verbose,
                debug=debug,
            )
        )

        if not quiet:
            results.print_summary()

        # Show debug output with server responses
        if debug:
            click.echo("\n" + "=" * 60)
            click.echo("DEBUG: SERVER RESPONSES")
            click.echo("=" * 60)
            for i, result in enumerate(results.individual_results, 1):
                click.echo(f"\n--- Request {i}: {result.user_id} ---")
                click.echo(f"Status Code: {result.status_code}")
                click.echo(f"Success: {result.success}")
                click.echo(f"Response Time: {result.response_time_ms:.2f}ms")
                if result.response_headers:
                    click.echo(f"Response Headers:")
                    for header, value in result.response_headers.items():
                        click.echo(f"  {header}: {value}")
                if result.error_message:
                    click.echo(f"Error: {result.error_message}")
                if result.response_body:
                    click.echo(f"Response Body:")
                    click.echo("-" * 40)
                    click.echo(result.response_body)
                    click.echo("-" * 40)
            click.echo("=" * 60 + "\n")

        if output:
            results_dict = results.to_dict()
            with open(output, "w") as f:
                json.dump(results_dict, f, indent=2)
            if not quiet:
                click.echo(f"Results saved to: {output}")

        # Exit with error code if there were failures
        if results.failed_requests > 0:
            sys.exit(1)

    except FileNotFoundError as e:
        click.echo(f"Error: File not found - {e}", err=True)
        sys.exit(2)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


@cli.command()
@click.option(
    "--issuer",
    "-i",
    required=True,
    help="SAML Issuer ID",
)
@click.option(
    "--sp-url",
    "-u",
    required=True,
    help="Service Provider URL",
)
@click.option(
    "--private-key",
    "-k",
    required=True,
    type=click.Path(exists=True),
    help="Path to private key",
)
@click.option(
    "--certificate",
    "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to certificate",
)
@click.option(
    "--user-id",
    "-U",
    default="testuser",
    help="User ID for the assertion (default: testuser)",
)
@click.option(
    "--email",
    "-e",
    help="User email address",
)
@click.option(
    "--groups",
    "-g",
    multiple=True,
    help="Groups to include",
)
@click.option(
    "--attribute",
    "-a",
    multiple=True,
    type=(str, str),
    help="Custom attributes as name value pairs",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output file for the SAML response XML",
)
@click.option(
    "--base64",
    "-b",
    is_flag=True,
    help="Output as base64 encoded (for POST binding)",
)
def generate(
    issuer: str,
    sp_url: str,
    private_key: str,
    certificate: str,
    user_id: str,
    email: Optional[str],
    groups: tuple,
    attribute: tuple,
    output: Optional[str],
    base64: bool,
):
    """Generate a single signed SAML assertion.

    Useful for testing or debugging SAML configuration.

    Example:
        saml-perf generate -i https://idp.example.com -u https://sp.example.com/acs \\
            -k private.key -c certificate.pem -U john.doe -g admins
    """
    try:
        builder = SAMLAssertionBuilder(
            issuer=issuer,
            sp_url=sp_url,
            private_key_path=private_key,
            certificate_path=certificate,
        )

        # Convert attributes
        custom_attributes = {}
        for name, value in attribute:
            if name in custom_attributes:
                if isinstance(custom_attributes[name], list):
                    custom_attributes[name].append(value)
                else:
                    custom_attributes[name] = [custom_attributes[name], value]
            else:
                custom_attributes[name] = value

        groups_list = list(groups) if groups else None

        if base64:
            result = builder.build_signed_response(
                user_id=user_id,
                user_email=email,
                groups=groups_list,
                custom_attributes=custom_attributes if custom_attributes else None,
            )
        else:
            result = builder.build_signed_response_xml(
                user_id=user_id,
                user_email=email,
                groups=groups_list,
                custom_attributes=custom_attributes if custom_attributes else None,
            )

        if output:
            with open(output, "w") as f:
                f.write(result)
            click.echo(f"SAML response saved to: {output}")
        else:
            click.echo(result)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--output-dir",
    "-o",
    default=".",
    type=click.Path(),
    help="Directory to output the generated keys (default: current directory)",
)
@click.option(
    "--key-name",
    "-n",
    default="saml",
    help="Base name for key files (default: saml)",
)
@click.option(
    "--cn",
    default="SAML Test IdP",
    help="Common Name for the certificate (default: SAML Test IdP)",
)
@click.option(
    "--days",
    "-d",
    default=365,
    type=int,
    help="Certificate validity in days (default: 365)",
)
def generate_keys(
    output_dir: str,
    key_name: str,
    cn: str,
    days: int,
):
    """Generate a self-signed certificate and private key for testing.

    Creates a private key and self-signed X.509 certificate suitable
    for signing SAML assertions.

    Example:
        saml-perf generate-keys -o ./keys -n test-idp --cn "My Test IdP"
    """
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from datetime import datetime, timedelta, timezone

        # Create output directory if needed
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "SAML Performance Test"),
        ])

        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.now(timezone.utc))
            .not_valid_after(datetime.now(timezone.utc) + timedelta(days=days))
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None),
                critical=True,
            )
            .sign(private_key, hashes.SHA256())
        )

        # Write private key
        key_path = Path(output_dir) / f"{key_name}.key"
        with open(key_path, "wb") as f:
            f.write(
                private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        # Write certificate
        cert_path = Path(output_dir) / f"{key_name}.crt"
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        click.echo(f"Generated private key: {key_path}")
        click.echo(f"Generated certificate: {cert_path}")
        click.echo(f"\nCertificate details:")
        click.echo(f"  Common Name: {cn}")
        click.echo(f"  Valid for:   {days} days")
        click.echo(f"  Key size:    2048 bits")

    except ImportError:
        click.echo("Error: cryptography library required. Install with: pip install cryptography", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("results_file", type=click.Path(exists=True))
def report(results_file: str):
    """Display a formatted report from a JSON results file.

    Example:
        saml-perf report results.json
    """
    try:
        with open(results_file, "r") as f:
            data = json.load(f)

        click.echo("\n" + "=" * 60)
        click.echo("SAML PERFORMANCE TEST REPORT")
        click.echo("=" * 60)
        click.echo(f"\nTotal Requests:     {data['total_requests']}")
        click.echo(f"Successful:         {data['successful_requests']}")
        click.echo(f"Failed:             {data['failed_requests']}")
        click.echo(f"Success Rate:       {data['success_rate']}")
        click.echo(f"\nTotal Time:         {data['total_time_seconds']} seconds")
        click.echo(f"Requests/Second:    {data['requests_per_second']}")

        rt = data.get("response_times_ms", {})
        click.echo(f"\nResponse Times (ms):")
        click.echo(f"  Average:          {rt.get('avg', 'N/A')}")
        click.echo(f"  Min:              {rt.get('min', 'N/A')}")
        click.echo(f"  Max:              {rt.get('max', 'N/A')}")
        click.echo(f"  Median:           {rt.get('median', 'N/A')}")
        click.echo(f"  95th Percentile:  {rt.get('p95', 'N/A')}")
        click.echo(f"  99th Percentile:  {rt.get('p99', 'N/A')}")

        if data.get("error_summary"):
            click.echo(f"\nError Summary:")
            for error, count in data["error_summary"].items():
                click.echo(f"  [{count}x] {error}")

        click.echo("=" * 60 + "\n")

    except json.JSONDecodeError:
        click.echo(f"Error: Invalid JSON file: {results_file}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI"""
    cli()


if __name__ == "__main__":
    main()

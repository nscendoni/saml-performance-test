# SAML Performance Test Tool

A command-line tool for performance testing SAML 2.0 Service Providers by sending multiple concurrent signed SAML assertions.

## Features

- **Concurrent SAML Assertions**: Send multiple SAML assertions simultaneously with different users
- **Configurable Groups**: Include configurable group attributes in SAML assertions
- **Custom Attributes**: Add any custom SAML attributes to assertions
- **Signed Assertions**: All assertions are properly signed using RSA-SHA256
- **Performance Metrics**: Detailed statistics including response times, success rates, and percentiles
- **Key Generation**: Built-in tool to generate test certificates and keys

## Installation

```bash
# Clone or navigate to the project directory
cd saml-performance-test

# Install dependencies
pip install -r requirements.txt

# Install the tool
pip install -e .
```

## Quick Start

### 1. Generate Test Keys

If you don't have a signing key and certificate, generate them:

```bash
saml-perf generate-keys -o ./keys -n test-idp --cn "My Test IdP"
```

This creates:
- `keys/test-idp.key` - Private key for signing
- `keys/test-idp.crt` - Certificate

### 2. Run a Performance Test

```bash
saml-perf test \
    --sp-url https://your-sp.example.com/saml/acs \
    --issuer https://your-idp.example.com \
    --private-key ./keys/test-idp.key \
    --certificate ./keys/test-idp.crt \
    --users 100 \
    --concurrency 10 \
    --groups admins \
    --groups users \
    --verbose
```

### 3. Generate a Single Assertion (for debugging)

```bash
saml-perf generate \
    --issuer https://your-idp.example.com \
    --sp-url https://your-sp.example.com/saml/acs \
    --private-key ./keys/test-idp.key \
    --certificate ./keys/test-idp.crt \
    --user-id john.doe \
    --email john.doe@example.com \
    --groups admins
```

## Commands

### `saml-perf test`

Run a SAML performance test.

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--sp-url` | `-u` | Service Provider ACS URL (required) | - |
| `--issuer` | `-i` | SAML Issuer/Entity ID (required) | - |
| `--private-key` | `-k` | Path to private key (required) | - |
| `--certificate` | `-c` | Path to certificate (required) | - |
| `--users` | `-n` | Number of users to simulate | 10 |
| `--concurrency` | `-j` | Max concurrent requests | 5 |
| `--groups` | `-g` | Groups to include (repeatable) | - |
| `--attribute` | `-a` | Custom attribute (name value) | - |
| `--timeout` | `-t` | Request timeout in seconds | 30 |
| `--no-verify-ssl` | - | Disable SSL verification | false |
| `--output` | `-o` | Save results to JSON file | - |
| `--verbose` | `-v` | Show progress | false |
| `--quiet` | `-q` | Suppress output | false |

### `saml-perf generate`

Generate a single signed SAML assertion.

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--issuer` | `-i` | SAML Issuer ID (required) | - |
| `--sp-url` | `-u` | Service Provider URL (required) | - |
| `--private-key` | `-k` | Path to private key (required) | - |
| `--certificate` | `-c` | Path to certificate (required) | - |
| `--user-id` | `-U` | User ID for assertion | testuser |
| `--email` | `-e` | User email address | - |
| `--groups` | `-g` | Groups to include (repeatable) | - |
| `--attribute` | `-a` | Custom attribute (name value) | - |
| `--output` | `-o` | Save to file | - |
| `--base64` | `-b` | Output as base64 | false |

### `saml-perf generate-keys`

Generate a self-signed certificate and private key.

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output-dir` | `-o` | Output directory | . |
| `--key-name` | `-n` | Base name for files | saml |
| `--cn` | - | Certificate Common Name | SAML Test IdP |
| `--days` | `-d` | Validity period | 365 |

### `saml-perf report`

Display a formatted report from JSON results.

```bash
saml-perf report results.json
```

## Examples

### Basic Test with Groups

```bash
saml-perf test \
    -u https://sp.example.com/saml/acs \
    -i https://idp.example.com \
    -k private.key \
    -c certificate.crt \
    -n 50 \
    -j 10 \
    -g admins \
    -g editors \
    -v
```

### Test with Custom Attributes

```bash
saml-perf test \
    -u https://sp.example.com/saml/acs \
    -i https://idp.example.com \
    -k private.key \
    -c certificate.crt \
    -n 100 \
    -j 20 \
    -g users \
    -a department Engineering \
    -a location "New York" \
    -o results.json
```

### High-Concurrency Stress Test

```bash
saml-perf test \
    -u https://sp.example.com/saml/acs \
    -i https://idp.example.com \
    -k private.key \
    -c certificate.crt \
    -n 1000 \
    -j 100 \
    -g users \
    --no-verify-ssl \
    -t 60 \
    -v \
    -o stress-test-results.json
```

## Output

The test produces statistics including:

- **Total Requests**: Number of assertions sent
- **Success/Failure Count**: How many succeeded or failed
- **Success Rate**: Percentage of successful requests
- **Requests/Second**: Throughput
- **Response Times**: Average, min, max, median, p95, p99

Example output:

```
============================================================
SAML PERFORMANCE TEST RESULTS
============================================================

Total Requests:     100
Successful:         98
Failed:             2
Success Rate:       98.00%

Total Time:         5.23 seconds
Requests/Second:    19.12

Response Times (ms):
  Average:          245.32
  Min:              45.12
  Max:              1234.56
  Median:           198.45
  95th Percentile:  567.89
  99th Percentile:  1012.34

Error Summary:
  [2x] HTTP 503
============================================================
```

## SAML Assertion Structure

The generated SAML assertions include:

- **NameID**: User identifier
- **Issuer**: Identity Provider entity ID
- **Conditions**: Time-based validity constraints
- **AuthnStatement**: Authentication context
- **AttributeStatement**: User attributes including:
  - `uid` - User ID
  - `email` - User email (if provided)
  - `groups` - Group memberships (multi-valued)
  - Custom attributes as specified

## Requirements

- Python 3.8+
- lxml
- signxml
- cryptography
- requests
- click
- aiohttp

## How to test with AEMaaCS
1. Create key and certificate: `aml-perf generate-keys -o ./keys -n test-idp --cn "My Test IdP"`
1. Import the certificate to AEM and copy the value of `certalias___xxx`
1. Prepare a configuration file like:
```
{
  "groupMembershipAttribute":"groups",
  "handleLogout":true,
  "identitySyncType":"idp_dynamic",
  "idpCertAlias":"certalias___1768900834257",
  "idpIdentifier":"saml-idp",
  "idpUrl":"$[env:SAML_IDP_URL;default=http://localhost:8081/realms/sling/protocol/saml]",
  "keyStorePassword":"admin",
  "logoutUrl":"$[env:SAML_LOGOUT_URL;default=http://localhost:8081/realms/sling/protocol/saml]",
  "nameIdFormat":"urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
  "path":[
    "/content/wintergw2025/us/en/saml-authenticated"
  ],
  "serviceProviderEntityId":"http://localhost:4503/content/wintergw2025/us/en/saml-authenticated/saml_login",
  "spPrivateKeyAlias":"aem-sp",
  "storeSAMLResponse":true,
  "synchronizeAttributes":[
    "urn:oid:2.5.4.42=givenName",
    "urn:oid:2.5.4.4=surname"
  ],
  "useEncryption":false,
  "userIntermediatePath":"/saml"
}
```
Remark that you need to set:
- `idpCertAlias`
- `serviceProviderEntityId`
- `groupMembershipAttribute`
1. Deploy the project
1. You can test with the a command like
```
saml-perf test  --issuer saml-idp     --sp-url http://localhost:4503/content/wintergw2025/us/en/saml-authenticated/saml_login     --private-key ./keys/test-idp.key     --certificate ./keys/test-idp.crt       --groups admins -n 10
```

## License

Apache 2.0 License

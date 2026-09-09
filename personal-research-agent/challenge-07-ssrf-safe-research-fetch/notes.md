# Working notes

- Inspected all remote research-agent branches and the Challenge 6 build log before selecting this task.
- Challenge 6 explicitly handed off to an SSRF-resistant browser/research tool.
- DNS validation alone is insufficient: a normal HTTP client can resolve again after validation. The transport therefore connects to the selected validated IP while preserving the original hostname for the HTTP Host header and TLS SNI/certificate verification.
- Reject a hostname if any DNS answer is non-public, rather than relying on address-selection order.
- Re-run the full URL, domain, port, DNS, and IP policy for every redirect.
- Verify the actual connected peer belongs to the validated DNS answer set.
- Disable compression and cap bytes while reading so compressed-response expansion cannot bypass the accounting model.
- Record URL, DNS answers, peer IP, status, redirect, bytes, and SHA-256 for every completed hop.
- Initial test run: 11 passed and 1 failed because the HTTPS-downgrade control preempted the redirect-IP assertion.
- Corrected the fixture to keep HTTPS while targeting the link-local metadata address; final run: 12 passed in 0.23 seconds.

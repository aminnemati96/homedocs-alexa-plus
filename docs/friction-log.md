# Friction log

Problems hit while building HomeDocs with Amazon tools, in the order they happened.

## 1. boto3 cannot use `aws login` credentials without an extra package

- **Task:** call Bedrock from a Python script using the credentials from `aws login`.
- **Steps:** `aws login` in the CLI, then `boto3.client("bedrock-runtime")` in a new uv project.
- **Expected:** boto3 picks up the same credentials the CLI uses.
- **Actual:** `MissingDependencyException: Using the login credential provider requires an additional dependency. You will need to pip install "botocore[crt]"`.
- **Severity:** Low. The message names the fix.
- **Workaround:** depend on `boto3[crt]` instead of `boto3`.
- **Suggestion:** mention `boto3[crt]` in the Bedrock Python getting-started pages next to `aws login`, or ship the login provider without the CRT dependency.

## 2. Anthropic use-case form error arrives in the middle of a conversation

- **Task:** first tool-use conversation with Claude Haiku 4.5 through the Converse API.
- **Steps:** Converse call returns a `toolUse`; the follow-up Converse call with the `toolResult` is sent.
- **Expected:** if the account must submit a use-case form, the very first call fails with an access error that says so.
- **Actual:** the first call succeeded; the second failed with `ResourceNotFoundException: Model use case details have not been submitted for this account`.
- **Severity:** Medium. "Not found" sent me looking for a wrong model ID first.
- **Workaround:** submit the form in the Bedrock console and wait about 15 minutes.
- **Suggestion:** use `AccessDeniedException` with a link to the form, and fail consistently from the first call.

## 3. `ServiceUnavailableException` on the US inference profile, no hint about global

- **Task:** answer a question from the web app with `us.anthropic.claude-haiku-4-5-20251001-v1:0`.
- **Expected:** a normal answer, as from the CLI a few minutes earlier.
- **Actual:** `ServiceUnavailableException ... (reached max retries: 3): Bedrock is unable to process your request.`
- **Severity:** Medium. Hard to tell whether the bug was mine.
- **Workaround:** switch to the global inference profile `global.anthropic.claude-haiku-4-5-20251001-v1:0`; no errors since.
- **Suggestion:** when a geographic profile is out of capacity, say so in the error and suggest the global profile.

## 4. AgentCore MCP sessions answer the MCP session DELETE with 404

- **Task:** call the MCP server hosted on AgentCore Runtime from the official MCP Python SDK.
- **Steps:** open a session with `streamable_http_client`, call a tool, close the session.
- **Expected:** a clean close.
- **Actual:** every call ends with `Session termination failed: 404` printed by the SDK.
- **Severity:** Low. Only noise, but it looks like a failure in a demo.
- **Workaround:** `terminate_on_close=False`. The AgentCore samples already pass this but never say why.
- **Suggestion:** accept the DELETE (or return 405), and explain the flag in the MCP hosting guide.

## 5. AgentCore MCP guide is Linux and CLI only

- **Task:** deploy the MCP server with Terraform from Windows.
- **Actual:** the guide uses the `agentcore` CLI and a bash script with `jq` to create Cognito. The Terraform resource `aws_bedrockagentcore_agent_runtime` exists and works well, but the guide does not mention it, and the Cognito client-credentials setup (domain, resource server, scopes) has to be pieced together from other pages.
- **Severity:** Medium for Windows users.
- **Workaround:** wrote the Terraform from the provider docs (see `infra/`).
- **Suggestion:** add a Terraform or CloudFormation tab, and a machine-to-machine Cognito example, since an agent calling an MCP server is the common case.

## 6. AgentCore samples use a deprecated MCP client function

- **Task:** copy the remote-invocation sample.
- **Actual:** the sample uses `streamablehttp_client`, which MCP SDK 1.30 marks deprecated in favour of `streamable_http_client` with an `httpx` client for headers.
- **Severity:** Low.
- **Suggestion:** update the samples.

## 7. ARM64-only images are slow to build on x86 Windows

- **Task:** build the MCP server image for AgentCore.
- **Actual:** AgentCore requires `linux/arm64`, so Docker Desktop on an x86 PC builds under emulation, which takes several minutes per build.
- **Severity:** Low.
- **Workaround:** keep dependency layers cached; build only when code changes.
- **Suggestion:** state the ARM64 requirement at the top of the guide and point to the S3 code-deploy option for Python projects, which avoids Docker entirely.

## 8. CloudFront OAC in front of a Lambda function URL cannot take plain POST bodies

- **Task:** put the agent's function URL behind CloudFront with origin access control, so only CloudFront can call it.
- **Actual:** with OAC, POST and PUT requests need the browser to compute a SHA-256 of the body and send it as `x-amz-content-sha256`. That is awkward for JSON and multipart uploads from a web page.
- **Severity:** Medium.
- **Workaround:** function URL with auth `NONE`, plus a secret header that CloudFront adds and the app checks.
- **Suggestion:** let CloudFront compute the payload hash for OAC-signed requests to Lambda.

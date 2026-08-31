# MCP Marketplace Publishing

This repository publishes a local `stdio` server. A package appearing on PyPI
does not cause it to appear in an IDE's MCP search surface. Discovery requires
separate Registry or directory publication.

## What The Repository Automates

- `README.md` contains the PyPI ownership proof required by the official MCP
  Registry: `mcp-name: io.github.jumodada/drissionpage-mcp`.
- `server.json` describes the immutable PyPI package, its `stdio` transport,
  source repository, and Registry server name.
- `.github/workflows/publish-mcp-registry.yml` runs on a `v<version>` tag. It
  validates release metadata, publishes to PyPI, waits for the release to be
  queryable, and publishes to the MCP Registry using GitHub OIDC.

The Registry is currently preview software. Its listing is the canonical public
MCP discovery record; it does not itself guarantee inclusion in an IDE-specific
marketplace.

## One-Time Owner Setup

1. In the PyPI project settings for `drissionpage-mcp`, add a trusted publisher
   with GitHub owner `jumodada`, repository `Drissionpage-MCP-Server`, workflow
   filename `publish-mcp-registry.yml`, and environment name `pypi`.
2. Confirm that GitHub Actions may use the `pypi` environment. Add any required
   deployment approval policy there before publishing.
3. Do not add a PyPI API token to the repository. The workflow uses short-lived
   OIDC credentials instead.

## Release Procedure

1. Merge the version, changelog, `server.json`, and release-workflow changes.
2. Confirm the Git tag, `pyproject.toml`, `drissionpage_mcp.__version__`, and
   both versions in `server.json` are identical.
3. Create and push the release tag, for example:

   ```bash
   git tag v0.8.7
   git push origin v0.8.7
   ```

4. Approve the GitHub `pypi` environment if it is protected, then wait for the
   `Publish package and MCP Registry entry` workflow to finish.
5. Search the official MCP Registry for
   `io.github.jumodada/drissionpage-mcp` and verify the linked PyPI version and
   repository URL before announcing the release.

PyPI versions and Registry versions are immutable. Correct a failed release by
publishing a new patch version; do not retag a released version.

## Cursor And TRAE Distribution

- **Cursor:** Cursor documents `cursor.directory` as the community discovery
  surface for MCP servers. After the Registry listing is live, submit the
  Registry page and this repository there. Users can always install the local
  server through `.cursor/mcp.json` or **Settings -> Tools & MCPs -> New MCP
  Server** using `command: "drissionpage-mcp"`.
- **TRAE:** TRAE documents MCP server configuration and installation links, but
  does not currently publish a public self-service MCP marketplace submission
  process. Publish the Registry listing and repository first, then distribute
  TRAE's generated install link or the documented local `stdio` configuration.
  An in-product search listing requires a TRAE partner or support-channel
  submission when that program is available.

The user-facing setup snippets remain in `README.md` and `README_CN.md`.

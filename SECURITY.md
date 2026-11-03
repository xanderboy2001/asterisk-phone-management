# Security policy

## Supported versions

Only the latest code on the `main` branch receives security fixes.

## Reporting a vulnerability

Please report vulnerabilities privately using the **Report a vulnerability**
button on this repository's **Security** tab. Don't open a public issue,
pull request, or discussion about a suspected vulnerability.

Include:

- what the problem is and where it is (file, function, or page)
- steps to reproduce it, or a proof of concept
- the impact you expect, for example reading voicemail PINs or registering
  as another phone

You'll get a reply once the report has been reviewed. Valid reports are
fixed privately and published as a GitHub security advisory after the fix
is released. Reporters are credited in the advisory unless they prefer
not to be.

## Scope

In scope: this repository's code, including the CLI, web UI, REST API, and
the configuration files it writes.

Out of scope:

- Behaviour that is documented as intended, such as the web UI having no
  login unless `ASTERISK_CLI_WEB_AUTH=basic` is set, or voicemail PIN
  resets using the extension number.
- Vulnerabilities in Asterisk, Cisco phone firmware, or third-party
  dependencies. Report those to their maintainers.
- Problems that need an attacker to already have root access to the
  server.

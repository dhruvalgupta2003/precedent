# See it in 2 minutes

You'll load 15 real decisions from [Backstage](https://backstage.io), a popular open-source project, and see
Precedent catch a change that goes against one of them. No account or AI key needed.

## Before you start

You need two free tools. You only install them once.

- **git** downloads the example. Most Macs already have it; if not, [download it](https://git-scm.com/downloads).
- **uv** installs and runs Precedent. You install it with one command, below.

Open your **Terminal** (on a Mac, press ⌘ Space and type "Terminal"; on Windows, open "PowerShell") and install uv:

=== "Mac and Linux"

    ```sh
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

=== "Windows"

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

Then close the Terminal and open it again.

## 1. Download Precedent

Copy these two lines into the Terminal and press Enter:

```sh
git clone https://github.com/dhruvalgupta2003/precedent
cd precedent
```

Precedent brings its own small database, so there's nothing else to install or start. (On Windows, run the demo in
[WSL](https://learn.microsoft.com/windows/wsl/install), or use a database server as
[Set it up](setup.md#1-install) explains.)

## 2. Load the example decisions

```sh
uv run precedent load examples/backstage
```

The first time takes about a minute while uv gets everything ready. Then you'll see:

<div class="pc-terminal" markdown>

```text
Loaded 15 decisions into 'team': 15 new or changed, 0 already up to date.
```

</div>

One of these decisions, ADR010, says: **use Luxon for dates, not Moment.**

## 3. Check a change that goes against it

This example change adds `moment-timezone`, a library that brings Moment back:

```sh
uv run precedent check --diff examples/changes/adds-moment-timezone.diff
```

<div class="pc-terminal" markdown>

```text
Precedent BLOCK: this change touches decisions the team recorded.
- team/ADR010 says avoid moment-timezone: "moment-timezone is an add-on that brings in Moment (precedent.yaml)" (examples/backstage/adr010-luxon-date-library.md)
```

</div>

<div class="pc-verdicts" markdown>
<div class="pc-verdict is-block" markdown>
<span class="pc-verdict-name"><span class="pc-icon">🛑</span>Stop</span>

Precedent caught it. It names the decision (ADR010), what to avoid, why, and where the note is.
</div>
</div>

## 4. Check a change that's fine

This one uses Luxon, as the team decided:

```sh
uv run precedent check --diff examples/changes/uses-luxon.diff
```

<div class="pc-terminal" markdown>

```text
Precedent CLEAR: no current decision is against this change.
```

</div>

## Try the other examples

There are two more example changes. Both get 🛑 Stop:

- `uses-react-function-component.diff` writes `React.FunctionComponent`, another name for something ADR006 avoids.
- `adds-node-fetch-native.diff` adds a copy of a library that ADR014 avoids.

```sh
uv run precedent check --diff examples/changes/uses-react-function-component.diff
uv run precedent check --diff examples/changes/adds-node-fetch-native.diff
```

## When you're done

Nothing keeps running in the background. The demo's decisions are kept in a small file
(`~/.local/share/precedent/precedent.db`) that you can delete.

**Next:** [set it up for your team](setup.md).

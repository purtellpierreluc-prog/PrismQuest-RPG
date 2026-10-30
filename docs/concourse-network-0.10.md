# The Concourse / Reimagined 0.10.0

## Playable Now

Open Town > Concourse, or Chronicle > Concourse / Network. Enter the local test
realm to create a separate realm character. This does not import or change a
solo chronicle, the browser game's Supabase database, or its ladder. The badge
distinguishes local/shared test data from a Steam-authenticated realm.
There are no fake player listings or simulated chat messages.

- Server-owned Arena outcomes, leveling, equipment, proficiency and drops.
- Optional one-time sandbox kit: level 45, common tier-45 gear, 2,000 gold and
  four finds. Existing starting items are kept. Never enabled in a live realm.
- Parties of one to five: invitation codes, ready checks, leader movement,
  automatic shared combat, existing Labyrinth class abilities/tank roles,
  boss progression, 25-second prism voting and reconnectable checkpoints.
- Bazaar escrow, purchases, change-price, cancellation and a transaction ledger.
  A price change invalidates a buyer's old confirmation.
- Pack/vault equipment and direct courier delivery by realm-specific vault code.
- Guild creation, invitation codes, membership, private guild chat and town chat.
- An indexed realm progression ladder, not a Steam leaderboard.

The realm combat preview resolves an encounter on the authority and sends its
compact result. It does not stream every damage animation over a socket. All
party members use the same checkpoint and monster outcome. An explicit **Leave
Party** ends an active run for everyone; merely disconnecting does not. Earned
progress remains. Gear/trading/training are locked during an active expedition
to prevent restoring an old snapshot over a transferred or equipped item.

## Local Data and Traffic

The default preview is embedded: no HTTP service is opened and no internet
request occurs. Its SQLite database is in `realm-preview/realm.sqlite3` beneath
the selected desktop profile. The test identity is in
`realm-preview-identity.json`. Neither is a solo save or Steam credential.

Normal solo play does not initialize the realm or add polling. The Concourse's
party view checks revisions every three seconds; unchanged snapshots do not
rerender. Other tabs refresh on actions or **Refresh Realm**, so typing, item
inspection and price dialogs do not have a polling parent. Chat is deliberately
manual refresh in this preview. HTTP snapshots use ETags and 304 responses.
Client requests and chat history are bounded. The ladder has its own SQL index.

Every mutation runs in one `BEGIN IMMEDIATE` transaction. Items have persistent
IDs, one owner/location, escrow and explicit courier claims. Trades adjust both
wallets and write both receipts atomically. Commands carry idempotency keys;
uncertain requests are persisted locally for safe replay after a process restart.
Bearer tokens are stored hashed on the service and expire after 24 hours.
**Reconnect Realm** reauthenticates without clearing its server checkpoint.

## Test Multiple Clients

Use disposable directories beneath `.local-test`, not a normal save profile:

```powershell
.\.venv\Scripts\python.exe tools/run_realm_server.py --sandbox --data-dir .local-test/shared-realm --port 8766
```

The access key is written to `.local-test/shared-realm/sandbox-access.key`, never
printed. In each separately launched desktop test profile, choose Concourse >
Developer Test Service, keep `http://127.0.0.1:8766`, and enter that key. Each
profile gets its own identity. The sandbox listener and developer connection
refuse non-loopback addresses; this is not public authentication.

For a reproducible real-socket integration check:

```powershell
.\.venv\Scripts\python.exe tools/realm_network_smoke.py --port 8766 --key-file .local-test/shared-realm/sandbox-access.key --output .local-test/shared-realm/report.json
```

The script exercises five independent clients, trading, direct delivery, guild
privacy, a shared Labyrinth and unchanged-snapshot responses.

## Steam Integration Boundary

Uploading the executable does **not** host a realm, authenticate Steam users or
automatically enable friends invitations. No borrowed App ID, Steamworks SDK
DLL, publisher key or production backend credentials are included.

The prepared backend authenticates `GetAuthTicketForWebApi` tickets using Steam's
documented `AuthenticateUserTicket` endpoint. It derives identity only from
Steam's verified response, not a submitted SteamID. Missing configuration and
sandbox-to-live identity mixing fail closed. The publisher key is server-only.

`NetworkController.steam(url, ticket_provider, name, player_class)` is the client
hook. The licensed native provider must wait for `GetTicketForWebApiResponse_t`,
return a ticket for identity `prismquest-realm`, and cancel it after exchange.
This native SDK provider is **not implemented or live-tested** without the
owner's real App ID and chosen licensed SDK bridge. Friends/overlay invitations,
Steam lobbies, Steam Cloud, achievements and Steam leaderboards remain separate
platform work; codes currently provide the invitation flow.

Before any public rollout:

1. Obtain the App ID and Windows Depot ID; select/license and implement the native
   SDK adapter. Verify ownership/family-sharing policy with real Steam accounts.
2. Configure server-only `PRISMQUEST_STEAM_APP_ID` and
   `PRISMQUEST_STEAM_PUBLISHER_KEY`. Run the service without `--sandbox`, behind
   HTTPS. Never put that key or the sandbox access key in a desktop package.
3. Provision durable storage, monitored backups/restore, TLS, request timeouts,
   deployment migrations, account revocation and administrative audit tooling.
   SQLite is appropriate for this single-service prototype, not a claim of
   distributed/multi-region production readiness.
4. Add moderation/reporting/blocking, guild officer/transfer tools, privacy/data
   retention policy, pagination beyond the preview's bounded result windows,
   and inventory/request-log retention limits before opening a public economy.
5. Decide online progression scope. This first realm supports feeder characters,
   Arena and shared Labyrinth progression; the complete solo Prismatic Quest,
   saved-set/transmutation/companion loop is not yet server-authoritative online.
6. Load-test representative parties; test reconnects, process restarts, wallet
   conservation, multi-account isolation and Steam authentication on real builds.
   Public rollout and migration of existing browser players require a separate
   explicit decision. There is deliberately no local-save upload endpoint.

Primary references: [Steam authentication](https://partner.steamgames.com/doc/features/auth),
[ticket verification](https://partner.steamgames.com/doc/webapi/ISteamUserAuth),
[Steam lobbies](https://partner.steamgames.com/doc/features/multiplayer/matchmaking).
The ECC testing guidance is used as a checklist, not imported as executable code.

## Verification

- 222 automated regressions, including 32 realm tests: ownership, escrow,
  simultaneous buyers, stale prices, courier claims, equipment swaps, guild
  privacy, party permissions, boss rewards, voting and restart-safe replay.
- Five independent HTTP clients tested against an actual loopback service.
- Source and packaged Concourse flows: 12 scene/viewport checks each, with
  no external requests or browser JavaScript errors.
- Existing solo workspaces tested at viewport sizes from 800x500 to 2560x1080.
- Native WebView2 launch and installed-package integrity checked separately.
- Pre-change 0.9.0 full executable folder preserved in
  `.build-backups/reimagined-0.9.0-9821b9c/PrismQuest`.

These checks do not substitute for real Steam authentication, public-network
load testing, moderation, release rights review or a production security audit.

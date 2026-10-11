# Provider formats: verified scope and real-data gate

Checked: 2026-10-11. Both real-format validation gates are **BLOCKED** because no owner-approved, anonymized, secret-free sample was supplied for this Nexus task.

| Provider | Official export information verified | Message schema verified in Nexus | Import behavior |
|---|---|---|---|
| ChatGPT | Official settings/privacy-request ZIP export includes chat/account data [1] | None for real exports | Accept only nexus_fixture=synthetic-v1 with provider=chatgpt |
| Claude | Official export includes conversations/account data, with plan and owner restrictions [2] | None for real exports | Accept only nexus_fixture=synthetic-v1 with provider=claude |

Official export instructions are not a versioned complete field specification. Do not infer that an unreviewed mapping/chats/message shape is supported. Larger archives, multiple JSON files, attachments, branching conversations, edited/regenerated answers, tool outputs and timestamp conventions all require approved evidence. V1's single-JSON synthetic ZIP parser must not be presented as a real export parser.

## Current adapters

`ADAPTERS` selects an explicitly provider-labelled `SyntheticAdapter`. The ChatGPT and Claude fixtures have separate collection/identity/title/role/text fields. Both produce the same Conversation/Message structure while preserving external IDs, raw source role values, source timestamp strings and SHA-256 content hashes. Observation timestamps and source/account namespaces are added by the store.

Within a fixture, repeated conversation IDs or message IDs are rejected. Across imports, identical messages are skipped; changed content, role or occurrence time under the same identity aborts the entire transaction. Missing messages in a later partial export are not deleted or silently interpreted as authoritative source deletions. Conversation titles can change, with transactional reindexing.

Synthetic fixture identity rules are not evidence about real provider revision semantics. Raw role labels are preserved rather than guessing how real tool/media messages should map.

## Required evidence before a real adapter can be enabled

1. Obtain explicit authorization for a minimal anonymized sample from each provider. Remove names, contacts, file contents/links, cookies, secrets, credentials and account identifiers.
2. Keep samples private and outside Git-tracked paths. Do not upload chat archives or credential material to the public repository.
3. Record export date, relevant plan/workspace, observed structure, redaction scope and format fingerprint without private payloads.
4. Cover Japanese and Unicode, long threads, branch/revision semantics, source IDs/times, tool/non-text content, deleted/partial coverage and unexpected fields.
5. Implement a real adapter under a new verified parser contract, keeping synthetic fixtures and existing PASS evidence unchanged.
6. Re-run 1,000-message zero-duplicate reimport, the original 30 token assertions, the additive fixed 30 mixed-language cases, transactional rejection and provenance checks on explicitly authorized real-format samples.
7. Complete the remaining privacy, browser and Windows ACL checks in the security review before importing private chats.

Until both provider families pass their actual-format gates, **V1 official PASS is forbidden**, regardless of CI.

## Sources

1. [Official ChatGPT export instructions](https://help.openai.com/en/articles/7260999-exporting-your-chatgpt-history-and-data)
2. [Official Claude export instructions](https://support.claude.com/en/articles/9450526-export-your-claude-data)

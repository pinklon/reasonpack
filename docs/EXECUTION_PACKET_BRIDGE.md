# ReasonPack and Execution Packets

## The short distinction

**ReasonPack preserves context. Execution Packet governs a particular job.**

They are complementary, not competing formats.

## ReasonPack asks

> What source-derived material should survive this session?

It packages:

- source metadata;
- normalized media/audio;
- transcript + provenance;
- technical metadata;
- byte identities.

A ReasonPack is useful even if nobody ever executes an agent against it.

## Execution Packet asks

> What exact work should be performed, against which exact inputs, under what authority, and what evidence counts as completion?

A governed Execution Packet can add:

- objective/intent;
- exact input references;
- accepted starting state;
- allowed/prohibited actions;
- required capabilities;
- execution policy;
- acceptance criteria;
- stop/recovery conditions;
- receipt contract.

## Composition model

```text
YouTube source
    ↓
ReasonPack build + verify
    ↓
verified source/context artifact
    ↓
Execution Packet references exact pack/member identities
    ↓
capable executor selected at runtime
    ↓
Execution Receipt
```

## Example

A ReasonPack alone might represent:

> “Here are the exact media/transcript/metadata bytes for this architecture talk.”

An Execution Packet could then represent:

> “Using this exact transcript and source metadata, compare the architecture claims to our supplied standards. You may read these inputs and write one local report. Do not access external systems. Evaluate these four acceptance criteria and write the required execution receipt.”

The first is durable context. The second is governed work.

## Why not put the job inside ReasonPack?

Because source evidence and work authority have different lifecycles.

One ReasonPack may support:

- a summary;
- an architecture review;
- a training handout;
- a counterargument analysis;
- a later research update.

Those are different jobs against the same source artifact.

If the job definition is embedded as the ReasonPack’s identity, every new use case forces unnecessary repackaging of the source evidence.

## Why not put the media inside every Execution Packet?

You can carry bytes when appropriate, but the packet should be able to reference exact immutable inputs rather than duplicating large context artifacts for every job.

This is the same separation that keeps reusable Skills from becoming one-off work manifests.

## Current reference-kit boundary

The ReasonPack runtime in this kit does **not** automatically create Execution Packets.

The bridge is architectural guidance and a roadmap direction.

That means the following are not current commands:

```text
reasonpack execute ...
reasonpack packetize ...
reasonpack run-with-codex ...
```

If such capabilities are added, they should be explicit adapters with their own tests and receipts.

## Future adapter requirements

A credible ReasonPack → Execution Packet adapter should:

1. require a successfully verified pack;
2. reference exact member SHA-256 identities;
3. keep storage/carrier location separate from semantic input identity;
4. avoid embedding credentials;
5. make provider/executor selection late-bound unless mission semantics require one;
6. require acceptance/stop/receipt semantics from the user/workflow;
7. never mutate the original ReasonPack merely to make execution convenient.

## Strategic value

This bridge demonstrates a larger pattern:

```text
reusable context + explicit work contract + replaceable executor + receipt
```

The interesting architecture is not that one script can call one model. It is that the context and the job can remain durable while the worker changes.

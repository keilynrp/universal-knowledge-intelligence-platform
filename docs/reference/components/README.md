# UKIP V1 Component Contracts

These contracts describe the current React implementation and the approved property surface that may be mirrored in Figma. React source remains authoritative until the Professional Figma library is built and linked.

## Status Vocabulary

| Status | Meaning |
| --- | --- |
| Draft | Contract is documented from current code but still has known accessibility, token, or coverage gaps. |
| Contract implemented | The documented React contract and dedicated tests are implemented on this branch. |
| Figma pending | Approved React props and visual states are mapped, but the Figma component awaits Professional buildout. |

## Component Index

| Component | React contract | Figma | Dependency |
| --- | --- | --- | --- |
| [Button](Button.md) | Contract implemented | Figma pending | Foundation |
| [Badge](Badge.md) | Contract implemented | Figma pending | Foundation |
| [Input](Input.md) | Contract implemented | Figma pending | Foundation |
| [Select](Select.md) | Contract implemented | Figma pending | Foundation |
| [PageHeader](PageHeader.md) | Draft | Figma pending | Button for common actions |
| [StatCard](StatCard.md) | Draft | Figma pending | DeltaBadge |
| [TabNav](TabNav.md) | Draft | Figma pending | Badge semantics |
| [EmptyState](EmptyState.md) | Draft | Figma pending | Button semantics |
| [ErrorBanner](ErrorBanner.md) | Draft | Figma pending | Button and danger semantics |
| [Skeleton](Skeleton.md) | Draft | Figma pending | Surface and layout tokens |

## Dependency Order

1. Build token variables and foundation components: Button, Badge, Input, Select.
2. Build composition components: PageHeader, StatCard, TabNav.
3. Build feedback and loading components: EmptyState, ErrorBanner, Skeleton.

Figma properties must map only to the public React props and visual states documented here. New Figma-only variants require a React contract change before adoption.

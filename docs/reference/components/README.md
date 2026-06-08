# UKIP V1 Component Contracts

These contracts describe the current React implementation and the approved property surface that may be mirrored in Figma. React source remains authoritative until the Professional Figma library is built and linked.

## Status Vocabulary

| Dimension | Values | Meaning |
| --- | --- | --- |
| Contract | Draft, Implemented | Whether the documented React contract is considered stable and implemented. |
| Token migration | Pending, Partial, Complete | Whether component visual classes have migrated to approved tokens; intentional local palettes do not prevent Complete. |
| Accessibility | Pending review, Reviewed with follow-ups, Contract covered | Whether accessibility is unreviewed, reviewed with documented gaps, or implemented and covered by the current contract/tests. |
| Figma | Pending Professional buildout | Approved React props and visual states are mapped, but the Figma component is not yet built. |

Dimensions are independent. For example, an implemented React contract may still have pending token migration or accessibility follow-ups.

## Component Index

| Component | Contract | Token migration | Accessibility | Figma | Dependency |
| --- | --- | --- | --- | --- | --- |
| [Button](Button.md) | Implemented | Partial | Contract covered | Pending Professional buildout | Foundation |
| [Badge](Badge.md) | Implemented | Complete | Reviewed with follow-ups | Pending Professional buildout | Foundation |
| [Input](Input.md) | Implemented | Complete | Contract covered | Pending Professional buildout | Foundation |
| [Select](Select.md) | Implemented | Complete | Contract covered | Pending Professional buildout | Foundation |
| [PageHeader](PageHeader.md) | Draft | Complete | Reviewed with follow-ups | Pending Professional buildout | Button for common actions |
| [StatCard](StatCard.md) | Draft | Complete | Reviewed with follow-ups | Pending Professional buildout | DeltaBadge |
| [TabNav](TabNav.md) | Draft | Pending | Reviewed with follow-ups | Pending Professional buildout | Badge semantics |
| [EmptyState](EmptyState.md) | Draft | Partial | Reviewed with follow-ups | Pending Professional buildout | Button semantics |
| [ErrorBanner](ErrorBanner.md) | Draft | Pending | Reviewed with follow-ups | Pending Professional buildout | Button and danger semantics |
| [Skeleton](Skeleton.md) | Draft | Pending | Reviewed with follow-ups | Pending Professional buildout | Surface and layout tokens |

## Dependency Order

1. Build token variables and foundation components: Button, Badge, Input, Select.
2. Build composition components: PageHeader, StatCard, TabNav.
3. Build feedback and loading components: EmptyState, ErrorBanner, Skeleton.

Figma properties must map only to the public React props and visual states documented here. New Figma-only variants require a React contract change before adoption.

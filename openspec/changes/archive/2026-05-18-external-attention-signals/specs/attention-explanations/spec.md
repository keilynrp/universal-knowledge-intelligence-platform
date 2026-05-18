## ADDED Requirements

### Requirement: Deterministic attention explanations
The system SHALL generate deterministic explanations for high or changing external attention.

#### Scenario: Policy mention explanation
- **WHEN** policy observations contribute materially to the score
- **THEN** the system SHALL include an explanation with `type: "policy_mention"` and evidence based on policy mention count and contribution

#### Scenario: Spike explanation
- **WHEN** attention increases sharply in a timeline period
- **THEN** the system SHALL include an explanation with `type: "attention_spike"` and the period responsible for the increase

#### Scenario: Sparse evidence fallback
- **WHEN** observations do not include titles, URLs, or snippets
- **THEN** the system SHALL still return an explanation based on source counts and period deltas

### Requirement: Explanation limits
The system SHALL return a compact explanation list suitable for executive UI surfaces.

#### Scenario: Limit explanations
- **WHEN** more than five explanations are available
- **THEN** the system SHALL return only the top five, ordered by decision relevance

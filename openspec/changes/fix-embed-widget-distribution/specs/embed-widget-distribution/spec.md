## ADDED Requirements

### Requirement: Embed snippets are usable without hand-editing

The system SHALL generate embed snippets whose URLs resolve in the deployment
that produced them, without the consumer substituting any value.

#### Scenario: Snippets carry no developer-machine host

- **WHEN** `GET /embed/{token}/snippet` is requested from a deployment whose
  public URLs are configured
- **THEN** neither the iframe snippet nor the JS snippet contains `localhost`

#### Scenario: API base comes from configuration

- **WHEN** `UKIP_PUBLIC_API_URL` is set
- **THEN** the JS snippet fetches from that origin

#### Scenario: API base falls back to the request origin

- **WHEN** `UKIP_PUBLIC_API_URL` is not set
- **THEN** the JS snippet fetches from the origin the snippet request itself
  arrived on
- **AND** the snippet still contains no hardcoded host

#### Scenario: Base URLs are normalized

- **WHEN** a configured base URL is supplied with a trailing slash
- **THEN** the generated URLs contain no doubled separator

### Requirement: The iframe snippet targets the rendering page

The system SHALL point the iframe snippet at the application route that renders
the widget, not at an API path.

#### Scenario: Iframe URL is the frontend embed route

- **WHEN** a snippet is generated for a widget token
- **THEN** the iframe `src` is the application's `/embed/{token}` route derived
  from `FRONTEND_URL`
- **AND** the snippet contains no `/frame` path

#### Scenario: The referenced route exists

- **WHEN** the path component of the generated iframe `src` is compared against
  the application's routes
- **THEN** it corresponds to an implemented route

### Requirement: Embed routes are framable, the rest of the app is not

The system SHALL permit framing of embed routes while continuing to forbid
framing of every other route.

#### Scenario: Embed route omits the blanket deny

- **WHEN** the application serves a route under `/embed/`
- **THEN** the response does not carry `X-Frame-Options: DENY`
- **AND** the response's `frame-ancestors` directive is not `'none'`

#### Scenario: Non-embed routes remain denied

- **WHEN** the application serves any route outside `/embed/`
- **THEN** the response carries `X-Frame-Options: DENY`
- **AND** its `frame-ancestors` directive is `'none'`

#### Scenario: Restricted widget limits its ancestors

- **WHEN** an embed route is served for a widget whose `allowed_origins` names
  specific origins
- **THEN** the response's `frame-ancestors` directive lists exactly those origins

#### Scenario: Open widget permits any ancestor

- **WHEN** an embed route is served for a widget whose `allowed_origins` is `*`
- **THEN** the response's `frame-ancestors` directive permits any origin

### Requirement: The JS snippet renders presentable output

The system SHALL generate a JS snippet that renders labelled widget values
rather than a serialized data dump.

#### Scenario: Snippet does not emit raw JSON

- **WHEN** a JS snippet is generated
- **THEN** it does not render the payload via a raw serialization of the data
  object
- **AND** it renders labelled values for the widget's type

#### Scenario: Snippet is dependency-free

- **WHEN** a JS snippet is generated
- **THEN** it references no external script or stylesheet

### Requirement: Token-based embed access is documented as token-bearing

The system SHALL document that the widget token is the access credential and
that `allowed_origins` restricts framing rather than data retrieval.

#### Scenario: Origin restriction is not presented as data protection

- **WHEN** an operator configures `allowed_origins` on a widget
- **THEN** the interface states that the setting controls which sites may embed
  the widget, and that anyone holding the token can retrieve the data directly

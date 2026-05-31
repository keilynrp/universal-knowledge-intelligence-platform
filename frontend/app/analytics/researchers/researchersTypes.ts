export type ScoreDrivers = {
  topic_match: number;
  publication_signal: number;
  citation_signal: number;
  recency_signal: number;
  authority_signal: number;
  quality_signal: number;
};

export type ResearcherEvidence = {
  entity_id: number;
  title: string | null;
  secondary_label: string | null;
  citations: number;
};

export type Researcher = {
  name: string;
  orcid: string | null;
  openalex_id: string | null;
  records_count: number;
  citation_count: number;
  topic_score: number;
  drivers: ScoreDrivers;
  evidence: ResearcherEvidence[];
};

export type TopicFilters = {
  source: string | null;
  year_from: number | null;
  year_to: number | null;
  country: string | null;
  institution: string | null;
  min_citations: number;
};

export type ExecutiveSummary = {
  topic: string;
  confidence: number;
  coverage_score: number;
  network_density_score: number | null;
  high_confidence_researchers: number;
  total_citations: number;
  top_researcher: Researcher | null;
  headline: string;
  stakeholder_value: string;
};

export type ResearchersPayload = {
  domain_id: string;
  topic: string;
  filters: TopicFilters;
  records_analyzed: number;
  researcher_count: number;
  researchers: Researcher[];
  executive_summary: ExecutiveSummary;
};

export type GraphNode = {
  id: string;
  type: "topic" | "researcher";
  label: string;
  score: number;
  records_count?: number;
  citation_count?: number;
};

export type GraphEdge = {
  source: string;
  target: string;
  type: "works_on_topic" | "coauthor_with";
  weight: number;
};

export type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  summary: {
    researcher_count: number;
    relationship_count: number;
    records_analyzed: number;
    top_researcher: Researcher | null;
    executive_summary: ExecutiveSummary;
  };
};

export type PositionedNode = GraphNode & { x: number; y: number };

export type FilterForm = {
  source: string;
  yearFrom: string;
  yearTo: string;
  country: string;
  institution: string;
  minCitations: string;
};

export const DRIVER_LABELS: Array<{ key: keyof ScoreDrivers; label: string }> = [
  { key: "topic_match", label: "Tema" },
  { key: "publication_signal", label: "Produccion" },
  { key: "citation_signal", label: "Citas" },
  { key: "recency_signal", label: "Recencia" },
  { key: "authority_signal", label: "Autoridad" },
  { key: "quality_signal", label: "Calidad" },
];

export const EMPTY_FILTERS: FilterForm = {
  source: "",
  yearFrom: "",
  yearTo: "",
  country: "",
  institution: "",
  minCitations: "",
};

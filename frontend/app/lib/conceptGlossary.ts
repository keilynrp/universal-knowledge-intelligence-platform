export type ConceptKey = "entity";

export interface ConceptDefinition {
  titleKey: string;
  definitionKey: string;
  fallbackTitle: string;
  fallbackDefinition: string;
}

export const CONCEPT_GLOSSARY: Record<ConceptKey, ConceptDefinition> = {
  entity: {
    titleKey: "concept.entity.title",
    definitionKey: "concept.entity.definition",
    fallbackTitle: "Entity",
    fallbackDefinition:
      "The canonical, traceable, and relatable unit UKIP uses to represent an object of knowledge, such as a person, institution, publication, concept, place, or dataset. It may consolidate multiple source records without erasing their provenance.",
  },
};

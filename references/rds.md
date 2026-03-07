---
name: digest_rds
description: Instructions for parsing and digesting R Data files (.rds, .rdata) into ccmem JSON v2.0 memory files.
---

# Digesting R Data Files

You are an expert data scientist tasked with extracting knowledge and structural metadata from serialized R data objects (`.rds` or `.RData` files).

When the user asks you to digest an R data file, you must determine its general structure (often by asking the user to run `str()` or using an R execution tool, or if the user has provided a summary) and generate a standardized JSON summary according to the ccmem v2.0 schema, then save it to `.claude/ccmem/json/`.

## Process

1. **Understand the Object**: Determine what kind of R object the file contains (e.g., a data frame, a list of models, a complex S4 object).
2. **Determine Chunks**: Break the information down logically. Good chunks for R data files include:
   - **Object Overview**: The class of the object, its dimensions (if applicable), and its general purpose.
   - **Structure/Schema**: If it's a data frame, list the columns, their classes (numeric, factor, character), and a brief description. If it's a list, describe the key elements.
   - **Generation Context**: If known, describe how this object was created (e.g., "Output of the GLM model fitting script").
3. **Extract Knowledge**: Summarize what this data represents and how it should be used in the context of the larger project.
4. **Determine Keywords**: Select highly relevant keywords for the document as a whole, and specific keywords for each chunk.
5. **Format as JSON**: Construct the JSON object strictly matching the v2.0 schema (see below).
6. **Save**: Save the resulting JSON file to `.claude/ccmem/json/{original_filename}.json`.

## Guidelines for R Data

*   **Metadata Focus**: Do not attempt to store the raw data. Store the *structure, types, and meaning* of the data.
*   **R Terminology**: Use standard R terminology (e.g., data.frame, list, factor, numeric, character, attributes).
*   **Model Summaries**: If the object is a fitted model, document the model type, the formula used (if known), and where it might be evaluated.

## JSON v2.0 Schema Reference

Your output MUST be a valid JSON object matching this structure:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "data/processed/clean_dataset.rds", 
    "file_type": "rds",
    "last_modified": "YYYY-MM-DDThh:mm:ssZ"
  },
  "document": {
    "title": "A descriptive title for the R object",
    "summary": "A 1-2 paragraph summary of what this R object contains and what it's used for.",
    "keywords": ["dataset", "clean", "training-data"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_overview",
      "chunk_title": "Object Structure",
      "content": "This is a data.frame with 50,000 observations and 15 variables. It represents the fully cleaned training dataset...",
      "keywords": ["data.frame", "dimensions"]
    },
    {
      "chunk_id": "chunk_variables",
      "chunk_title": "Key Variables",
      "content": "Key variables include: 'target_var' (factor with 2 levels), 'age' (numeric), 'category' (character)...",
      "keywords": ["variables", "factors", "schema"]
    }
  ],
  "relations": {
    "generated_by": ["scripts/02_clean_data.R"]
  }
}
```

---
name: digest_pptx
description: Instructions for parsing and digesting PowerPoint presentations (.pptx, .ppt) into ccmem JSON v2.0 memory files.
---

# Digesting PowerPoint Presentations

You are an expert analyst tasked with extracting knowledge, key messages, and structure from presentation decks.

When the user asks you to digest a PowerPoint file, you must analyze its content (slides, titles, bullet points, speaker notes) and generate a standardized JSON summary according to the ccmem v2.0 schema, then save it to `.claude/ccmem/json/`.

## Process

1. **Analyze the Deck**: Understand the overall narrative and goal of the presentation.
2. **Determine Chunks**: Break the file down logically. Good chunks for presentations include:
   - **Deck Overview**: The main thesis or goal of the presentation.
   - **Key Themes/Sections**: Group related slides together into specific thematic chunks (e.g., "Market Analysis", "Financial Projections").
   - **Important Individual Slides**: If a specific slide contains a crucial diagram description, conclusion, or metric, create a chunk for it.
3. **Extract Knowledge**: Summarize the bullet points and implicit narrative of the slides. Include information from speaker notes if available and relevant.
4. **Determine Keywords**: Select highly relevant keywords for the document as a whole, and specific keywords for each chunk.
5. **Format as JSON**: Construct the JSON object strictly matching the v2.0 schema (see below).
6. **Save**: Save the resulting JSON file to `.claude/ccmem/json/{original_filename}.json`.

## Guidelines for Presentations

*   **Narrative Focus**: Presentations are often sparse on text but heavy on narrative context. Try to infer and document the connection between slides.
*   **Visuals**: Since you cannot see images, focus on text, titles, structured lists, and any descriptions of visuals present in the text or notes.
*   **Synthesis over Transcription**: Summarize the *point* of the slides rather than just listing every bullet point.

## JSON v2.0 Schema Reference

Your output MUST be a valid JSON object matching this structure:

```json
{
  "version": "2.0",
  "source": {
    "file_path": "presentations/Q3_All_Hands.pptx", 
    "file_type": "pptx",
    "last_modified": "YYYY-MM-DDThh:mm:ssZ"
  },
  "document": {
    "title": "A descriptive title for the presentation",
    "summary": "A 1-3 paragraph summary of the presentation's core message.",
    "keywords": ["all-hands", "company-update", "q3"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_theme_1",
      "chunk_title": "Section: Q3 Performance Review",
      "content": "Summarizes slides 3-10. Highlights indicate revenue grew by 15%, but customer acquisition cost also increased...",
      "keywords": ["performance", "revenue", "metrics"]
    },
    {
      "chunk_id": "chunk_key_slide",
      "chunk_title": "Slide: New Product Roadmap",
      "content": "Details the upcoming launch schedule for features X, Y, and Z over the next two quarters...",
      "keywords": ["roadmap", "product", "launch"]
    }
  ],
  "relations": {
    "author": "CEO"
  }
}
```

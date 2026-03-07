---
description: How to digest R script files (.R) into the v2.0 JSON memory schema
---

# R Script Digestion SKILL

## Purpose
This skill instructs you on how to read an R script file (`.R`) and produce a standardized JSON file (v2.0 schema) that describes its contents for long-term memory storage and retrieval.

## When to Use
Use this skill when asked to digest/ingest any file with the `.R` extension.

## Step-by-Step Instructions

### 1. Read the File
Open and read the entire `.R` file.

### 2. Identify the Document-Level Summary
Write a 1–2 sentence summary of the script's overall purpose. Ask yourself:
- What is this script trying to accomplish?
- What is the main input and main output?

### 3. Chunk the File
Split the script into logical chunks. Use the following granularity rules:

| Pattern | Chunk Boundary |
|---|---|
| Named functions (`function_name <- function(...)`) | Each function = 1 chunk |
| Comment section headers (`# ---- Section Name ----` or `#%%`) | Each section = 1 chunk |
| If no clear sections or functions exist | Split by logical blocks (~30–80 lines) |

### 4. For Each Chunk, Extract

- **chunk_title**: A short human-readable name (e.g., "Data Loading", "Model Training", "Plot Generation").
- **content**: A natural-language description of what this chunk does. Include:
  - What data it reads or transforms
  - What functions/packages it calls (e.g., `dplyr::mutate`, `caret::train`)
  - What output it produces (e.g., a data frame, a plot, a saved file)
  - Any hardcoded parameters or thresholds (e.g., `ntree = 500`)
- **keywords**: 3–8 relevant terms (package names, statistical methods, data names).

### 5. What to Ignore
- **Do NOT** include raw code verbatim in the `content` field. Describe it in natural language instead.
- **Skip** blank lines, commented-out dead code, and auto-generated headers (e.g., RStudio boilerplate).
- **Skip** trivial lines like `library(tidyverse)` as standalone chunks — instead, mention loaded packages in the relevant chunk's description.

### 6. Populate Relations
Scan the script for I/O operations and populate `reads_from` and `writes_to`:

| R Function | Relation |
|---|---|
| `read.csv()`, `read_csv()`, `fread()`, `read.table()`, `read_tsv()` | `reads_from` |
| `readRDS()`, `load()`, `readxl::read_excel()` | `reads_from` |
| `write.csv()`, `write_csv()`, `fwrite()`, `write.table()` | `writes_to` |
| `saveRDS()`, `save()`, `ggsave()`, `pdf()`, `png()` | `writes_to` |
| `source()` | `reads_from` (another R script) |

### 7. Handle Visuals
If the script generates plots (e.g., `ggplot()`, `plot()`, `hist()`):
- In the chunk `content`, describe the plot in natural language:
  - "Generates a scatter plot of `price` vs `sqft` colored by `region`."
  - "Saves a bar chart comparing Q3 revenue across 4 regions to `plots/q3_revenue.png`."
- Do NOT attempt to render or embed the image.

### 8. Output Format
Always output a single JSON file conforming to the v2.0 schema.

## Example

### Input: `analysis/churn_model.R`
```r
# ---- Load Data ----
library(tidyverse)
library(caret)

customers <- read_csv("data/clean_customers.csv")
customers <- customers %>%
  select(-customer_id) %>%
  mutate(income = ifelse(is.na(income), median(income, na.rm = TRUE), income))

# ---- Train Model ----
set.seed(42)
rf_model <- train(churn ~ ., data = customers, method = "rf",
                  trControl = trainControl(method = "cv", number = 5),
                  tuneGrid = data.frame(mtry = 3))

# ---- Save Output ----
saveRDS(rf_model, "models/rf_churn_model.rds")
cat("OOB Error:", rf_model$finalModel$err.rate[500, "OOB"], "\n")
```

### Output: `analysis/churn_model.R.json`
```json
{
  "version": "2.0",
  "source": {
    "file_path": "analysis/churn_model.R",
    "file_type": "r_script",
    "last_modified": "2024-03-05T14:30:00Z",
    "hash": "sha256:e4d909c290d0..."
  },
  "document": {
    "title": "Customer Churn Prediction Model",
    "summary": "Loads cleaned customer data, trains a Random Forest classifier using 5-fold CV, and saves the model as an RDS file.",
    "keywords": ["churn", "random forest", "caret", "classification", "cross-validation"]
  },
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "chunk_title": "Data Loading and Preprocessing",
      "content": "Loads customer data from 'data/clean_customers.csv' using readr. Drops the 'customer_id' column and handles missing values in the 'income' column using median imputation.",
      "keywords": ["read_csv", "tidyverse", "imputation", "clean_customers"]
    },
    {
      "chunk_id": "chunk_2",
      "chunk_title": "Model Training",
      "content": "Trains a Random Forest classifier to predict churn using the caret package. Uses 5-fold cross-validation. Hyperparameters: mtry=3. Random seed is set to 42 for reproducibility.",
      "keywords": ["caret", "random forest", "cross-validation", "mtry", "train"]
    },
    {
      "chunk_id": "chunk_3",
      "chunk_title": "Save Model Output",
      "content": "Saves the trained Random Forest model to 'models/rf_churn_model.rds' using saveRDS. Prints the final OOB error rate to the console.",
      "keywords": ["saveRDS", "OOB error", "model output"]
    }
  ],
  "relations": {
    "reads_from": ["data/clean_customers.csv"],
    "writes_to": ["models/rf_churn_model.rds"]
  }
}
```

## Output File Naming Convention
The JSON file should be named `<original_filename>.json` and placed alongside the source file or in the configured `json_output_dir`.
- `analysis/churn_model.R` → `analysis/churn_model.R.json`
- `scripts/data_prep.R` → `scripts/data_prep.R.json`

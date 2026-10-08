# How it works

lumen-napari is a thin layer between two existing tools. napari owns the pixels and the window. Lumen owns the chat, the planning, the SQL and the charts. lumen-napari gives Lumen actions and tools that read and change the napari viewer.

```text
napari (Qt main thread)                 browser
  layers, features, camera               Lumen chat
        ▲          │                         │
 writes │          │ reads                   │ websocket
 (main  │          ▼                         ▼
 thread)  lumen-napari ◄──────────── Lumen server (background thread)
          actions, tools,             planner → SQL / charts / analyses
          analyses                          │
               │                            ▼
               └──── tables ────────► DuckDB (one per session)
```

## One process

The chat server runs inside napari's Python process, on a background thread (`panel.serve(..., threaded=True)`), bound to `127.0.0.1`. That means:

- **No copies.** Tools read `layer.data` and `layer.features` directly, without serialising images between processes.
- **No open socket for code.** Nothing executes arbitrary code sent over the network. The LLM can only call the actions and tools listed in the [reference](../reference/chat_actions.md).
- **One lifetime.** The server stops when napari quits.

Qt requires that layers are changed on the main thread. Every write (adding a labels layer, setting colors, moving the camera) goes through `superqt`'s `ensure_main_thread`, and the worker thread waits for it to finish. Reads happen on the worker thread.

## The pieces in Lumen terms

| lumen-napari | Lumen concept | Role |
|---|---|---|
| `NapariControls` | source controls (`CodeSourceControls`) | Actions that produce tables: segment, measure, folders, regions |
| `ViewerTool`s | tools (`FunctionTool`) | Act on napari: show, color, filter, set pixel size, compare |
| `ObjectExplorer`, `PlateHeatmap` | analyses | Interactive plots that click back to napari |
| image upload handlers | `upload_handlers` | Turn dropped image files into napari layers |
| `NapariPlanner` | coordinator (`Planner`) | Lumen's planner, without clarifying questions |

### One database per session

Every table goes into a single DuckDB source for the chat session. When an action runs again (say after a hand edit), its table is replaced in place and Lumen's cache is cleared. Because all tables share one database, Lumen's SQL agent can join them: objects with a plate map, regions with measurements.

### Tools hand Lumen the table

After a tool changes napari, it also gives Lumen the current measurement table, its schema and a summary. A follow-up such as "now plot area against intensity" therefore works on the objects a tool just segmented, without a separate "load the table" step. The last few napari actions are passed along too, so the answer knows what was changed.

### Questions work in any order

Tools that need objects segment the first image layer when nothing is segmented yet. "Color the nuclei by area" works as a first question.

## Clicking back

- **Lumen charts** are Vega-Lite. lumen-napari adds a point selection on the identifying columns (`label`, `image_id`, `centroid_*`) to each chart whose rows are objects. A click sends that row back to Python.
- **Analyses** are HoloViews plots with a tap stream.

Either way the row is resolved to an object: a label on the labels layer it came from, an image from a folder (re-segmented with the recorded settings, so labels match the table), or a position on a whole slide. napari then centres, zooms and selects it.

## Showing the work

Each action posts a **napari** message in the chat with its settings, the object count, the units, and a PNG of the outlines on the image. These messages, the questions, and the charts are recorded on a `Script` object, which writes the [exported script and report](../how_to/export.md).

## Hand edits

A measured labels layer is watched for paint events. After a 500 ms pause, it is measured again, `features` is updated and the Lumen table replaced, so the chat always sees the current objects.

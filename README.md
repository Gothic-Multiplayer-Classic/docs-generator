# docs-luagmp – Documentation Generator

`docs-luagmp` is a Python-based documentation generator for the **Gothic Multiplayer** project.
It scans C/C++ source files for structured `/* luagmp (...) */` comment blocks and converts them into Markdown documentation using customizable templates.

Inspired by the [Gothic Online's DocsGenerator](https://gitlab.com/GothicMultiplayerTeam/docsgenerator), it also uses the same markdown documents for templates.

The generator is designed to be:
- Fast on large C++ codebases
- Deterministic and template-driven
- Compatible with existing `docsgenerator`-style templates
- Safe (missing tags never crash generation)

---

## Supported Source Files

By default, the generator scans **only** the following extensions:

- `.cpp`
- `.hpp`
- `.h`

All other files are ignored automatically.

---

## Requirements

- Python **3.9+**
- `jinja2`

Install dependency:
```bash
pip install jinja2
```

---

## Usage

```bat
python luagmp_docgen.py --project "J:\GitHub\GMPClassic" --out "J:\GitHub\gmpdocs" --templates "templates"
```

---

## Supported Documentation Blocks

Each documentation block must start with:

```cpp
/* luagmp (<type>)
 *
 * ...
 *
 */
```

Supported `<type>` values:

| Type          | Description |
|--------------|------------|
| `class`       | Class definition |
| `constructor`| Class constructor |
| `method`     | Class method |
| `property`   | Class property |
| `callback`   | Class callback |
| `func`       | Global function |
| `event`      | Event |
| `const`      | Constant |
| `global`     | Global value |

---

## Common Tags

| Tag | Description |
|----|------------|
| `@name` | Name of the entity |
| `@side` | `client`, `server`, `shared` |
| `@category` | Category / module |
| `@version` | Version string |
| `@deprecated` | Deprecation notice |
| `@param` | Function/method parameter |
| `@return` | Return value |
| `@notes` | Additional notes |
| `@extends` | Base class (classes only) |
| `@declaration` | C/C++ signature (optional) |
| `@example` | Example usage (multiline supported) |

All tags are optional unless required by your template.

---

## Example Blocks

### Class

```cpp
/* luagmp (class)
 *
 * Exposes Discord rich presence features.
 *
 * @name     Discord
 * @side     client
 * @category Discord
 * @version  0.1.0
 *
 */
```

### Method

```cpp
/* luagmp (method)
 *
 * Sets the draw position.
 *
 * @name setPosition
 * @param (int) x X position
 * @param (int) y Y position
 * @declaration
 * void setPosition(int x, int y);
 *
 */
```

### Property

```cpp
/* luagmp (property)
 *
 * Current draw position.
 *
 * @name position
 * @return ({x, y}) Position table
 *
 */
```

### Function

```cpp
/* luagmp (func)
 *
 * Set player instance.
 *
 * @name setPlayerInstance
 * @side client
 * @category Player
 * @param (int) player_id Player ID
 * @param (string) instance Instance name
 * @return (bool) Success
 *
 */
```

### Event

```cpp
/* luagmp (event)
 *
 * Triggered on chat message.
 *
 * @name onPlayerMessage
 * @side client
 * @category Player
 * @param (int) sender_id Sender
 * @param (string) message Text
 *
 */
```

### Constant

```cpp
/* luagmp (const)
 *
 * Escape key.
 *
 * @name KEY_ESCAPE
 * @side client
 * @category Key
 *
 */
```

---

## Output Structure

Generated documentation is written to the output directory using the following layout:

### Classes
```
<out>/client-classes/<category>/<ClassName>.md
```

Example:
```
gmpdocs/client-classes/discord/Discord.md
```

### Functions
```
<out>/client-functions/<category>/<FunctionName>.md
```

### Events
```
<out>/client-events/<category>/<EventName>.md
```

### Globals
```
<out>/client-globals/<category>/<GlobalName>.md
```

### Constants (aggregated per category)
```
<out>/client-constants/<category>/<Category>.md
```

---

## Templates

Templates are standard **Jinja2 Markdown** files.

Required template names:

- `class.md`
- `function.md`
- `event.md`
- `const.md`
- `global.md`

Templates may be provided as:
- a directory
- a `.zip` archive

If the zip contains a `templates/` subfolder, it is detected automatically.

---

## Notes on @declaration

- `@declaration` is **optional**
- If missing, no code block is rendered
- This avoids empty or broken Markdown sections
- Recommended for public C++ API only

---
title: '{{ definition.name }}'
---
# `{% if definition.static %}static {% endif %}class` {{ definition.name }}{% if definition.extends %} `extends` {{ definition.extends }}{% endif %} <font size="4">({{ definition.side.value }}-side)</font>
{% if definition.deprecated %}
!!! danger "Deprecated since version: {{ definition.deprecated }}"
{% elif definition.version %}
!!! info "Available since version: {{ definition.version }}"
{% endif %}
{% for note in definition.notes %}
!!! note
    {{ note }}
{% endfor %}

{{ definition.description }}

{% for constructor in constructors %}
### Constructor
```cpp
{{ definition.name }}.new({{ constructor.declaration }})
```

**Parameters:**

{% if constructor.params|length > 0 %}
{% for param in constructor.params %}
* `{{param.type}}` **{{param.name}}**: {{ param.description }}
{% endfor %}
{% else %}
No parameters.
{% endif %}
{% endfor %}

## Properties
{% if properties|length > 0 %}
{% for property in properties %}
### `{{ property.returns.type }}` {{ property.name }} {% if property.read_only %}<font size="2">(read-only)</font>{% endif %}

{% if property.deprecated %}
!!! danger "Deprecated since version: {{ property.deprecated }}"
{% elif property.version %}
{% if property.version != definition.version %}
!!! info "Available since version: {{ property.version }}"
{% endif %}
{% endif %}
{% for note in property.notes %}
!!! note
    {{ note }}
{% endfor %}

{{ property.description }}

----
{% endfor %}
{% else %}
No properties.

----
{% endif %}

## Methods
{% if methods|length > 0 %}
{% for method in methods %}
### {% if method.static %}`static` {% endif %}{{ method.name }}
{% if method.deprecated %}
!!! danger "Deprecated since version: {{ method.deprecated }}"
{% elif method.version %}
{% if method.version != definition.version %}
!!! info "Available since version: {{ method.version }}"
{% endif %}
{% endif %}
{% for note in method.notes %}
!!! note
    {{ note }}
{% endfor %}

{{ method.description }}

```cpp
{{ method.declaration }}
```

{% if method.params|length > 0 %}
**Parameters:**

{% for param in method.params %}
* `{{param.type}}` **{{param.name}}**: {{ param.description }}
{% endfor %}
{% endif %}
  
{% if method.returns %}
**Returns `{{ method.returns.type }}`:**

{{ method.returns.description }}
{% endif %}

----
{% endfor %}
{% else %}
No methods.

----
{% endif %}

## Callbacks
{% if callbacks|length > 0 %}
{% for callback in callbacks %}
### {% if callback.static %}`static` {% endif %}{{ callback.name }}
{% if callback.deprecated %}
!!! danger "Deprecated since version: {{ callback.deprecated }}"
{% elif callback.version %}
{% if callback.version != definition.version %}
!!! info "Available since version: {{ callback.version }}"
{% endif %}
{% endif %}
{% for note in callback.notes %}
!!! note
    {{ note }}
{% endfor %}

{{ callback.description }}

```cpp
{{ callback.declaration }}
```

{% if callback.params|length > 0 %}
**Parameters:**

{% for param in callback.params %}
* `{{param.type}}` **{{param.name}}**: {{ param.description }}
{% endfor %}
{% endif %}

{% if callback.returns %}
**Returns `{{ callback.returns.type }}`:**

{{ callback.returns.description }}
{% endif %}

----
{% endfor %}
{% else %}
No callbacks.

----
{% endif %}
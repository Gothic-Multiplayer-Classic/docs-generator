---
title: '{{ name }}'
---
# `function` {{ name }} <font size="4">({{ side.value }}-side)</font>
{% if deprecated %}
!!! danger "Deprecated since version: {{ deprecated }}"
{% elif version %}
!!! info "Available since version: {{ version }}"
{% endif %}
{% for note in notes %}
!!! note
    {{ note }}
{% endfor %}

{{ description }}

## Declaration
```cpp
{{ declaration }}
```

## Parameters
{% if params|length > 0 %}
{% for param in params %}
* `{{param.type}}` **{{param.name}}**: {{ param.description }}
{% endfor %}
{% else %}
No parameters.
{% endif %}
  
{% if returns %}
## Returns `{{ returns.type }}`
{{ returns.description }}
{% endif %}

{% if example_code %}
=== "Lua"

    ```js
    {{ example_code }}
    ```
{% endif %}

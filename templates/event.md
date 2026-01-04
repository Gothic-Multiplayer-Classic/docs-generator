---
title: '{{ name }}'
---
# `event` {{ name }} <font size="4">({{ side.value }}-side)</font>
{% if deprecated %}
!!! danger "Deprecated since version: {{ deprecated }}"
{% elif version %}
!!! info "Available since version: {{ version }}"
{% endif %}
{% if cancellable %}
!!! tip "This event can be canceled"
{% endif %}
{% for note in notes %}
!!! note
    {{ note }}
{% endfor %}

{{ description }}

## Parameters
{% if params|length > 0 %}
```c++
{{ declaration }}
```

{% for param in params %}
* `{{param.type}}` **{{param.name}}**: {{ param.description }}
{% endfor %}
{% else %}
No parameters.
{% endif %}

{% if example_code %}
=== "Lua"

    ```js
    {{ example_code }}
    ```
{% endif %}

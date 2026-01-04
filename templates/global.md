---
title: '{{ name }}'
---
# `{{ returns.type }}` {{ name }} <font size="4">({{ side.value }}-side)</font>
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

---
title: '{{ category }}'
---
# `constants` {{ category }} <font size="4">({{ side.value }}-side)</font>

| Name         | Description                          |
| :----------: | :----------------------------------- |
{% for const in elements %}
{% autoescape false %}
| `{{ const.name }}` | {{ const.description | replace("\n", "<br/>") }} |
{% endautoescape %}
{% endfor %}
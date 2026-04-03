# Test File with Triple Dashes

This tests handling of --- in content.

## Section Divider

---

The line above is a markdown horizontal rule (three dashes).

---

Another horizontal rule.

### Code Example

```yaml
---
title: YAML Front Matter
author: Test
---
```

The above code block contains --- which should be treated as content, not file headers.

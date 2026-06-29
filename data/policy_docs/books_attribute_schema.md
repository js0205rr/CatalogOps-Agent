---
doc_type: attribute_schema
category: Books
effective_date: 2026-01-01
source: "CatalogOps internal experimental policy summary"
risk_level: medium
---

# Books Attribute Schema

## Common Required Attributes

Book listings should provide:

- book_title
- author
- format
- language

## Category Specific Requirements

- Fiction and Non-Fiction require book_title, author, format, and language.
- Academic & Exam Prep requires book_title, author_or_editor, format, edition, and exam_or_subject.
- Children Books requires book_title, author_or_editor, format, and age_range.
- Reference requires book_title, author_or_editor, format, and language.
- Religion & Spirituality requires book_title, author_or_editor, format, and language.

## Missing Attribute Handling

Create missing_attribute when a required field is absent from merchant attributes and
cannot be inferred from title or description. Use this document as attribute_schema evidence.

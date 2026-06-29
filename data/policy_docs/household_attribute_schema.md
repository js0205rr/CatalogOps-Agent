---
doc_type: attribute_schema
category: Household
effective_date: 2026-01-01
source: "CatalogOps internal experimental policy summary"
risk_level: medium
---

# Household Attribute Schema

## Common Required Attributes

Household listings should provide:

- brand
- product_type
- material
- use_case

## Category Specific Requirements

- Home Decor requires brand, product_type, material, dimensions, and color.
- Kitchen & Dining requires brand, product_type, material, and capacity_or_size.
- Furniture requires brand, product_type, material, dimensions, and assembly_required.
- Bedding & Bath requires brand, product_type, material, size, and color.
- Storage & Organization requires brand, product_type, material, and dimensions.
- Cleaning Supplies requires brand, product_type, material, and use_case.
- Lighting requires brand, product_type, power_rating, and color_or_finish.

## Missing Attribute Handling

Create missing_attribute when a required field is absent and not inferable from product
text. Use this document as attribute_schema evidence.

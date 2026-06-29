---
doc_type: attribute_schema
category: Clothing & Accessories
effective_date: 2026-01-01
source: "CatalogOps internal policy summary based on public marketplace listing rules"
risk_level: medium
---

# Clothing Attribute Schema

## Common Required Attributes

For clothing listings, required attributes should be supplied when they are applicable
to the product type:

- brand
- product_type
- gender
- size
- color
- material

## Category Specific Requirements

Tops, Bottoms, Dresses, Clothing Sets, Innerwear, Shoes, and Apparel require brand,
product_type, gender, size, color, and material.

Bags require brand, product_type, color, and material.

Accessories require brand, product_type, color, and material.

Clothing Sets should also provide pieces_in_set when the title or description mentions
sets, packs, coordinated outfits, night suits, sleep suits, or tracksuits.

## Missing Attribute Handling

If a required attribute is absent from both merchant attributes and product text, mark
missing_attribute and reference this schema as attribute_schema evidence.

---
doc_type: category_policy
category: Household
effective_date: 2026-01-01
source: "CatalogOps internal experimental policy summary"
risk_level: medium
---

# Household Category Policy

## Scope

This policy applies to home, kitchen, decor, furniture, storage, cleaning, bedding,
bath, and lighting products.

## Category Routing

- Home Decor includes paintings, wall art, frames, clocks, vases, posters, and showpieces.
- Kitchen & Dining includes cookware, bottles, containers, plates, jars, knives, dinner sets, and kitchen tools.
- Furniture includes chairs, tables, desks, shelves, cabinets, wardrobes, racks, and sofas.
- Bedding & Bath includes bedsheets, blankets, pillows, towels, curtains, mattresses, and bath textiles.
- Storage & Organization includes boxes, baskets, organizers, hangers, holders, stands, and storage racks.
- Cleaning Supplies includes mops, brooms, brushes, dusters, wipes, scrubbers, and trash bags.
- Lighting includes lamps, bulbs, LED lights, lanterns, night lights, and decorative lighting.

## Decision Rule

If the product text clearly describes a Household product but seller_category points
to Electronics, Books, or Clothing, mark category_mismatch. If the item is a powered
home appliance or smart home device, use evidence to decide between Household and
Electronics; otherwise send to human_review.

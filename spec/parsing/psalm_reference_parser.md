# Psalm Reference Parser – Laag 1

Doel: psalmverwijzingen robuust parsen en normaliseren voor intent `psalm_lookup_1773`.

## Normalisatieregels
- Lowercase voor parsing; behoud originele cijfers.
- Voegwoorden → komma: vervang ` en `, ` & `, `&`, ` plus `, `plus` door `,`.
- Bereiken → koppelteken: vervang `t/m`, `tm`, `t m`, `tot en met`, `tot-en-met` door `-`.
- Trim overtollige spaties rond psalmnummer, dubbele punten en separators.

## Stap-voor-stap parsing
1. **Detectie**
   - Acceptabele prefixen: `psalm`, `ps.`, `ps` (optioneel) gevolgd door psalmnummer 1–150.
   - Versdeel herkend na `:` of `.` of na de woorden `vers` / `verzen`.
2. **Tokenisatie**
   - Pas normalisatie toe.
   - Split het versdeel op `,` of `;` (na normalisatie van voegwoorden).
   - Trim elk token; negeer lege tokens (leeg → invalid_request).
3. **Range-expansie**
   - Token met `-` → bereik. Parse `a-b` met integers.
   - Validatie range: `a >= 1`, `b >= 1`, `a <= b`.
   - Voeg alle integers `a..b` toe aan de verzameling.
4. **Losse verzen**
   - Token zonder `-` → enkel vers. Vereist integer `>= 1`.
5. **Resultaat bouwen**
   - `psalm_number`: integer 1–150 (anders `invalid_request`).
   - `verses`: unieke integers, oplopend gesorteerd. Vereist minimaal 1 vers.
   - Outputvorm: `{ intent: "psalm_lookup_1773", request: { psalm_number, verses }, status: "ok" }`.

## Validatieregels
- Psalmnummer: 1 ≤ n ≤ 150. Buiten bereik → `invalid_request`.
- Versnummer: integer ≥ 1. Niet-integer of ontbrekend versdeel → `invalid_request`.
- Ranges: vereisen `start ≤ end`. Anders `invalid_request`.
- Lege verslijst na parsing → `invalid_request`.

## Foutcodes
- `invalid_request`: parsing/validatie faalt (onleesbaar, ontbrekende verzen, buiten bereik).
- `not_found`: downstream plugin geeft 404/geen match.
- `verification_failed`: max-versen check faalt of plugin-antwoord wijkt af van bron.

## Output normalisatie
- De parser levert alleen status `ok` of `invalid_request`.
- Downstream responsen (plugin/verification) moeten conform `/spec/schemas/psalm_lookup_1773.response.schema.json` zijn.

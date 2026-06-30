export function parseDnaParam(params: URLSearchParams): boolean {
  return params.get("dna") !== "off" // default ON; only the literal "off" disables
}

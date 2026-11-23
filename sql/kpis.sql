-- Kennzahlen (KPIs) zur Ticket-Analyse.
-- Jede Abfrage beginnt mit "-- name: <name>" und wird von src/analyse.py ausgeführt.
-- Tabellen: incidents (1 Zeile je Ticket, Endstand), events (1 Zeile je Statusänderung)

-- name: ueberblick
SELECT COUNT(*)                                        AS tickets,
       ROUND(AVG(made_sla) * 100, 1)                   AS sla_quote_pct,
       ROUND(AVG(reassignment_count > 0) * 100, 1)     AS anteil_weitergeleitet_pct,
       ROUND(AVG(reopen_count > 0) * 100, 1)           AS anteil_wiedereroeffnet_pct,
       ROUND(AVG(resolution_hours), 1)                 AS mittlere_loesungszeit_h,
       MIN(opened_at)                                  AS zeitraum_von,
       MAX(opened_at)                                  AS zeitraum_bis
FROM incidents;

-- name: sla_nach_weiterleitungen
SELECT CASE WHEN reassignment_count >= 3 THEN '3+' ELSE CAST(reassignment_count AS TEXT) END
                                                       AS weiterleitungen,
       COUNT(*)                                        AS tickets,
       ROUND(AVG(made_sla) * 100, 1)                   AS sla_quote_pct,
       ROUND(AVG(resolution_hours), 1)                 AS mittlere_loesungszeit_h
FROM incidents
GROUP BY 1
ORDER BY 1;

-- name: sla_nach_prioritaet
SELECT priority                                        AS prioritaet,
       COUNT(*)                                        AS tickets,
       ROUND(AVG(made_sla) * 100, 1)                   AS sla_quote_pct,
       ROUND(AVG(resolution_hours), 1)                 AS mittlere_loesungszeit_h,
       ROUND(AVG(reassignment_count), 2)               AS weiterleitungen_schnitt
FROM incidents
GROUP BY 1
ORDER BY 1;

-- name: wiedereroeffnung
SELECT CASE WHEN reopen_count > 0 THEN 'wiedereröffnet' ELSE 'nicht wiedereröffnet' END AS status,
       COUNT(*)                                        AS tickets,
       ROUND(AVG(made_sla) * 100, 1)                   AS sla_quote_pct,
       ROUND(AVG(resolution_hours), 1)                 AS mittlere_loesungszeit_h
FROM incidents
GROUP BY 1;

-- name: zeit_je_status
-- Wie lange liegt ein Ticket in welchem Status, bis es gelöst ist?
-- LEAD() liefert den Zeitpunkt der nächsten Statusänderung desselben Tickets.
SELECT incident_state                                  AS status,
       ROUND(SUM(dauer_h), 1)                          AS stunden_gesamt,
       COUNT(DISTINCT number)                          AS tickets_mit_status
FROM (
    SELECT number, incident_state,
           (julianday(LEAD(sys_updated_at) OVER w) - julianday(sys_updated_at)) * 24 AS dauer_h
    FROM events
    WINDOW w AS (PARTITION BY number ORDER BY sys_updated_at, sys_mod_count)
)
WHERE dauer_h IS NOT NULL
  AND incident_state NOT IN ('Resolved', 'Closed', '-100')
GROUP BY 1
ORDER BY 2 DESC;

-- name: top_teams
-- Die 10 Teams mit den meisten Tickets: Wo entstehen Engpässe?
SELECT assignment_group                                AS team,
       COUNT(*)                                        AS tickets,
       ROUND(AVG(made_sla) * 100, 1)                   AS sla_quote_pct,
       ROUND(AVG(reassignment_count), 2)               AS weiterleitungen_schnitt,
       ROUND(AVG(resolution_hours), 1)                 AS mittlere_loesungszeit_h
FROM incidents
WHERE assignment_group IS NOT NULL
GROUP BY 1
ORDER BY tickets DESC
LIMIT 10;

-- name: tickets_pro_monat
SELECT strftime('%Y-%m', opened_at)                    AS monat,
       COUNT(*)                                        AS tickets,
       ROUND(AVG(made_sla) * 100, 1)                   AS sla_quote_pct
FROM incidents
GROUP BY 1
ORDER BY 1;

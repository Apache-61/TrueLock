# Reporte de gaps — TrueLock

**Fecha de corte:** 2026-09-12  
**Rama/commit revisado:** estado comprometido actual (`c885326`)  
**Estimación global de avance:** **40 %**

## Alcance y método

Se contrastó la implementación actual con el brief de `docs/challenge/`,
los contratos, la arquitectura, el runbook de demo y los archivos de
configuración. También se revisaron los artefactos que no tienen contenido
funcional: no hay archivos versionados de cero bytes, pero
`tests/e2e/` sólo contiene un README y los directorios de datos
`data/raw/`, `data/normalized/` y `data/synthetic/` son, en la práctica,
documentación sin datasets operables.

El porcentaje mide cumplimiento verificable de la solución y de la demo, no
la cantidad de archivos ni el hecho de que las pruebas unitarias pasen. Es
una estimación: el brief oficial del challenge aún no se encuentra en el
repositorio, por lo que no es posible calcular una cobertura de rúbrica
oficial.

Verificaciones ejecutadas:

- `pytest -q`: **171 passed, 1 skipped**. El omitido es la integración con
  PostgreSQL, que requiere `psql` y `DATABASE_URL`.
- `python scripts/verify_demo.py`: pasa las invariantes declaradas.
- `python scripts/run_demo.py`: el flujo local finaliza con el fallback.
- `npm run build` en `frontend/`: build y typecheck de Next.js exitosos.

## Progreso por capacidad

- **Modelo de dominio y contratos internos — 85 %**: modelos Pydantic,
  esquemas JSON, repositorios en memoria y pruebas de alineación están
  presentes.
- **Ingesta y datos de demo — 50 %**: existen parsers defensivos de CFDI XML
  y CSV bancario, además de un fixture sintético; falta conectarlos a una
  carga persistente y a escenarios introducidos por el juez.
- **Persistencia PostgreSQL — 25 %**: hay migraciones, seed SQL y una prueba
  opcional, pero no hay repositorios PostgreSQL ni la aplicación usa
  `DATABASE_URL`.
- **Detección y priorización — 30 %**: existen ciclos, pagos duplicados,
  pass-through y un control negativo; falta gran parte de la biblioteca
  documentada y la agregación determinista de señales.
- **Investigación, evidencia y caso — 25 %**: hay allowlist, límite de pasos,
  hash y fallback; la conclusión no se deriva de evidencia real ni de la
  exposición calculada.
- **API y frontend — 40 %**: hay un flujo REST mínimo que el frontend
  consume y compila; faltan endpoints comprometidos, eventos y
  visualizaciones basadas en datos del caso.
- **Pruebas, operación y documentación — 45 %**: CI, pruebas unitarias y
  build están activos; no hay E2E real, la integración de base de datos no
  se ejecutó y varios documentos describen rutas/contratos que ya no
  coinciden con el código.

## Ya completado

- Modelos canónicos para entidades, cuentas, facturas, pagos, transacciones,
  leads, evidencia, pasos de investigación y casos en
  `backend/src/truelock/domain/models/`.
- Validación de esquemas y una base de pruebas automatizadas que actualmente
  pasa.
- Repositorios en memoria con consultas deterministas y escenario sintético
  de ciclo de fondos, EFOS contextual y control legítimo.
- Parsers con rechazo explícito de registros inválidos para CFDI y CSV
  bancario.
- Tres detectores iniciales: ciclo, pago duplicado y pass-through, más un
  lead de control de dirección compartida.
- Cálculo de exposición de flujo raíz que evita sumar los hops intermedios.
- Cliente server-side de Gemini con allowlist de cinco herramientas y
  fallback sin credencial configurada.
- API FastAPI y UI Next.js para listar leads, iniciar investigación, mostrar
  timeline/evidencia/caso y hacer una pregunta.
- Migraciones SQL, Dockerfile, Docker Compose y CI de backend/build de
  frontend.

## Gaps prioritarios

### P1 — Requerido para una demo forense creíble

1. **Derivar la investigación y el caso de los registros reales.**  
   `ForensicInvestigator` marca el resultado según `risk_score`, asigna
   `amount_involved=1000000.0` y usa `lead.entity_id` como proveedor, sin
   resolver las contrapartes del rastro. No
   usa `EvidenceCollector.evaluate_finding()` ni convierte resultados de
   herramientas en afirmaciones comprobables. Debe calcular la exposición
   del flujo detectado, construir evidencia con source IDs/provenance y
   producir los tres estados: `SUBSTANTIATED`, `UNSUBSTANTIATED` e
   `INSUFFICIENT_EVIDENCE`.

2. **Corregir el loop del agente y el fallback.**  
   La ejecución observada en `scripts/run_demo.py` invoca repetidamente
   `trace_outgoing_funds` con `{"depth": 3}`; la herramienta requiere
   `account_id`, por lo que no recupera el rastro. Los tres pasos generan el
   mismo hash. Validar argumentos contra el esquema, conservar resultados de
   herramienta entre turnos, exigir evidencia nueva o estrechar la hipótesis
   en cada `FOLLOW`, y terminar por presupuesto con un `ESCALATE` registrado.

3. **Alinear la superficie de herramientas con su contrato.**  
   El contrato documenta catorce herramientas y exige
   `result`, `provenance`, `source_ids`, `execution_time` y `errors`.
   La implementación declara cinco y devuelve formas ad hoc. Elegir y
   documentar una superficie definitiva; implementar o retirar cada
   herramienta, con pruebas de contrato.

4. **Implementar persistencia de producto.**  
   Añadir repositorios PostgreSQL que satisfagan los protocolos y conectar
   `DATABASE_URL` a servicios/API. Hoy toda la sesión, leads, casos,
   evidencia y datos proceden de memoria. Ajustar Compose para cargar
   también el seed o incorporar un seeder explícito; actualmente sólo monta
   migraciones. Unificar además los datasets: `demo_scenario.py` contiene
   el ciclo canónico de $1M→$920k→$740k, mientras `001_demo.sql` carga el
   escenario distinto Acme/Proveedor con dos transacciones. La base de datos
   no puede validar ni reproducir el demo que usa la aplicación.

5. **Cerrar el contrato de demo/API.**  
   La aplicación expone `/api/leads`, `/api/investigations/start` y
   `/api/cases/{id}/questions`, mientras `docs/contracts/api.md` promete
   casos, grafo, evidencia, eventos, `/questions` e
   `/demo/inject-fraud`. Implementar los endpoints imprescindibles o
   actualizar el contrato. En particular, `POST /demo/inject-fraud`, el
   descarte visible de un lead y el stream de pasos son requerimientos
   explícitos del runbook.

6. **Hacer la visualización y Q&A auditables.**  
   `MoneyTrailGraph` muestra un caso fijo aunque se investigue otro lead.
   Debe construirse desde el caso/rastro seleccionado. La respuesta fallback
   de Q&A es genérica y no devuelve `evidence_refs`; debe citar evidencia y
   pasos recuperables o declarar insuficiencia.

### P2 — Cobertura funcional y calidad antes de endurecer operación

1. Completar la biblioteca de detectores documentada: factura duplicada,
   montos inusuales, concentración, conciliación factura-pago, fan-in,
   fan-out, red de empresas pantalla, correlación 69-B y timing inusual.
   Emitir `Signal` con IDs de fuente y agregar señales con pesos/umbrales
   documentados, en lugar de asignar riesgos constantes por detector.

2. Corregir el detector pass-through para evaluar tiempo real: las
   transacciones sólo almacenan fecha, aunque el demo afirma “<2 horas”.
   Ampliar el modelo/fuente con timestamp y verificar orden temporal,
   ventana y relación de montos. Normalizar/deduplicar el ciclo para no
   generar tres leads equivalentes desde cada nodo.

3. Conectar los parsers a importación de escenarios y crear fixtures/answer
   keys para cada patrón. Añadir la ingesta local de EFOS 69-B prevista,
   manteniendo su carácter contextual.

4. Añadir pruebas de integración reales contra PostgreSQL, pruebas de
   contrato API/herramientas, pruebas de componentes y E2E
   dataset→detector→caso→frontend. Convertir el README de `tests/e2e/` en
   pruebas ejecutables e incluir el fallback sin red.

5. Reparar la documentación desactualizada: `docs/testing.md` aún dice que
   no hay código de producto y refiere dependencias/rutas eliminadas; varios
   contratos apuntan a `domain/schemas/` pese a que los esquemas canónicos
   viven bajo `backend/src/truelock/domain/schemas/`.

### P3 — Robustez y preparación para despliegue

1. Usar de verdad el presupuesto de sesión, `config/agent-providers.yaml`,
   la telemetría de uso y el failover de proveedores; los valores existen en
   configuración pero no participan en el flujo.

2. Completar el despliegue documentado: servicio frontend en Compose,
   health/readiness checks de aplicación, configuración de producción y
   runbook de recuperación probado.

3. Mejorar trazabilidad operativa: persistir eventos, hashes completos,
   historial de investigación y métricas de detector/modelo. Añadir
   controles de concurrencia, paginación y manejo de errores visible en UI.

4. Reconciliar README, arquitectura, runbook y contratos tras cerrar P1/P2,
   para que no se presenten como capacidades terminadas antes de estar
   demostradas.

## Riesgos de demostración actuales

- El demo termina y las pruebas pasan, pero no prueba que el agente haya
  trazado fondos: el fallback observado produjo pasos repetidos sin cuenta
  de origen válida.
- Un caso de alta prioridad puede mostrar una cifra y proveedores que no
  pertenecen al lead investigado, porque se codifican de manera fija.
- PostgreSQL puede arrancar, pero la aplicación no lee ni escribe en él y el
  fixture SQL no se carga automáticamente con el Compose actual. Aunque se
  cargara manualmente, representa un escenario distinto al fixture en
  memoria que alimenta la demo.
- La UI da una impresión de flujo completo, aunque el grafo es estático y no
  existe el momento de fraude oculto/inyección que pide el runbook.

## Secuencia recomendada

Resolver P1 en este orden: evidencia/caso basado en datos → loop y contrato
de herramientas → repositorios PostgreSQL y carga de demo → API de inyección,
eventos y Q&A con referencias → grafo dinámico. Después completar P2 con
detectores y pruebas de regresión; dejar P3 para endurecimiento y despliegue.

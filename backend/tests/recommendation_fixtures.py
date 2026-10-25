"""Real separate file imports and human Decisions; no forged independence flag."""

from uuid import UUID, uuid4
from xml.sax.saxutils import escape

from app.conflicts.jobs import execute_conflict
from app.imports.jobs import execute_import
from app.matching.jobs import execute_matching
from app.normalization.jobs import execute_run
from tests.test_auth import ORIGIN
from tests.test_conflicts_integration import rows
from tests.test_conflicts_integration import start as conflict_start
from tests.test_decisions_integration import begin, save, selection
from tests.test_imports import upload
from tests.test_matching_integration import start as matching_start
from tests.test_normalization_integration import start as normalization_start
from tests.test_similarity_integration import index, similar


class Cases:
    def __init__(self, client):
        self.client = client
        self.settings = client.app.state.settings
        self.sources = []
        self.decisions = []
        self.cases = []
        self.prefix = uuid4().hex[:8]
        for source_type, role in [("FILE", "REGISTER_EXPORT"), ("ONE_C", "ACCOUNTING_EXPORT")]:
            response = client.post(
                "/api/v1/sources",
                headers=ORIGIN,
                json={
                    "code": uuid4().hex,
                    "name": "Synthetic declared " + role,
                    "source_type": source_type,
                },
            )
            assert response.status_code == 201, response.text
            self.sources.append(
                {"source_id": response.json()["id"], "source_type": source_type, "role": role}
            )

    def case(self, number=None, subject=None):
        number = str(len(self.cases)) if number is None else str(number)
        key = self.prefix + "-" + number
        subject = subject or (
            "Forest Keeper synthetic material bolt steel durable reference provenance "
            "group sample precision compatible independent item " + key
        )
        csv = f"id,name,mass,price,date\n{key},{subject},12.5 kg,10,2026-01-01\n".encode()
        xml = (
            f'<Выгрузка><Объект Тип="Справочник.Номенклатура" Ид="{escape(key)}">'
            f"<Наименование>{escape(subject)}</Наименование><Масса>12.4 kg</Масса>"
            "<Цена>10</Цена><Дата>2026-01-01</Дата></Объект></Выгрузка>"
        ).encode()
        runs = []
        for source, name, payload in zip(
            self.sources, ["material.csv", "onec.xml"], [csv, xml], strict=True
        ):
            response = upload(self.client, source["source_id"], name, payload)
            assert response.status_code in {200, 201}, response.text
            batch = response.json()["id"]
            execute_import(UUID(batch), self.settings)
            run = normalization_start(self.client, batch)
            execute_run(UUID(run["id"]), self.settings)
            runs.append(run["id"])
        matching = matching_start(self.client, runs)
        execute_matching(UUID(matching["id"]), self.settings)
        conflict = conflict_start(self.client, matching)
        execute_conflict(UUID(conflict["id"]), self.settings)
        found = rows(self.client, matching)
        assert len(found) == 1 and found[0]["conflict_type"] == "VALUE_MISMATCH", found
        identifier = found[0]["id"]
        card = self.client.get("/api/v1/conflicts/" + identifier).json()
        self.settings.recommendation_source_map = {
            "version": "synthetic-explicit-sources-v1",
            "approved": True,
            "approval_reference": "Isolated fixture operator explicitly assigns these two sources.",
            "domain": "synthetic-material",
            "entity_type": "Material",
            "attribute_code": "mass",
            "matching_profile_hashes": [card["basis"]["matching_profile_hash"]],
            "sources": self.sources,
        }
        self.cases.append(identifier)
        return identifier

    def confirm(self, identifier, source=0, **changes):
        review = begin(self.client, identifier)
        position = next(
            i
            for i, value in enumerate(review["selectable_values"])
            if value["source_id"] == self.sources[source]["source_id"]
        )
        body = {**selection(review, position), **changes}
        result = save(self.client, identifier, body)
        self.decisions.append(result)
        return result

    def prepared(self, count=5):
        for _ in range(count):
            self.confirm(self.case())
        query = self.case()
        index(self.settings)
        result = similar(self.client, query)
        assert len(result["results"]) == min(count, 5), result
        return query

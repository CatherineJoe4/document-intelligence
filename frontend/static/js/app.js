/* ============================================================
   CREDORA — FINANCIAL DOCUMENT INTELLIGENCE
   Application Controller
============================================================ */

"use strict";


/* ============================================================
   01. CONFIGURATION
============================================================ */

const API_BASE = "/api/v1";

const MAX_FILE_SIZE = 10 * 1024 * 1024;

const ALLOWED_EXTENSIONS = [
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png"
];

const ALLOWED_MIME_TYPES = [
    "application/pdf",
    "image/jpeg",
    "image/png"
];


/* ============================================================
   02. APPLICATION STATE
============================================================ */

const state = {

    currentPage: "dashboard",

    documents: [],

    filteredDocuments: [],

    selectedFile: null,

    currentResult: null,

    isProcessing: false

};


/* ============================================================
   03. DOM HELPERS
============================================================ */

const $ = (selector) => document.querySelector(selector);

const $$ = (selector) => document.querySelectorAll(selector);


function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


function isObject(value) {

    return (
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value)
    );
}


function isEmptyValue(value) {

    return (
        value === null ||
        value === undefined ||
        value === "" ||
        (
            typeof value === "string" &&
            value.trim().toLowerCase() === "null"
        )
    );
}


function formatValue(value) {

    if (isEmptyValue(value)) {
        return `<span class="missing-value">Not available</span>`;
    }

    if (typeof value === "boolean") {
        return value ? "Yes" : "No";
    }

    if (typeof value === "object") {
        return escapeHtml(JSON.stringify(value));
    }

    return escapeHtml(value);
}


function formatDate(value) {

    if (!value) {
        return "—";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return escapeHtml(value);
    }

    return date.toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit"
    });
}


function humanizeDocumentType(type) {

    const types = {
        invoice: "Invoice",
        balance_sheet: "Balance Sheet",
        profit_and_loss: "Profit & Loss",
        cash_flow_statement: "Cash Flow Statement"
    };

    return types[type] || humanizeKey(type || "Document");
}


function humanizeKey(value) {

    if (!value) {
        return "";
    }

    return String(value)
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/[_-]+/g, " ")
        .replace(/\s+/g, " ")
        .trim()
        .replace(/\b\w/g, letter => letter.toUpperCase());
}


function normalizeStatus(status) {

    if (!status) {
        return "—";
    }

    const normalized = String(status).toUpperCase();

    if (
        normalized === "PASS" ||
        normalized === "PASSED"
    ) {
        return "PASS";
    }

    if (
        normalized === "FAILED" ||
        normalized === "FAIL"
    ) {
        return "FAILED";
    }

    return normalized;
}


/* ============================================================
   04. API REQUEST HELPER
============================================================ */

async function apiRequest(
    endpoint,
    options = {}
) {

    const response = await fetch(
        `${API_BASE}${endpoint}`,
        {
            ...options,
            headers: {
                ...(options.headers || {})
            }
        }
    );

    let data = null;

    try {
        data = await response.json();
    } catch {
        data = null;
    }

    if (!response.ok) {

        const errorMessage =
            data?.error?.message ||
            data?.detail?.error?.message ||
            data?.detail ||
            data?.message ||
            `Request failed with status ${response.status}`;

        throw new Error(errorMessage);
    }

    return data;
}


/* ============================================================
   05. PAGE NAVIGATION
============================================================ */

function showPage(pageName) {

    const pages = $$(".page");

    pages.forEach(page => {

        page.classList.remove("active");

    });


    const targetPage = $(`#${pageName}`);

    if (!targetPage) {
        return;
    }

    targetPage.classList.add("active");

    state.currentPage = pageName;


    /* Update navigation */

    $$(".nav-button").forEach(button => {

        button.classList.toggle(
            "active",
            button.dataset.page === pageName
        );

    });


    /* Scroll to top */

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });


    /* Refresh page-specific data */

    if (pageName === "dashboard") {

        loadDocuments();

    }

    if (pageName === "documents") {

        loadDocuments();

    }
}


function setupNavigation() {

    $$("[data-page]").forEach(element => {

        element.addEventListener(
            "click",
            () => {

                const page =
                    element.dataset.page;

                if (page) {
                    showPage(page);
                }

            }
        );

    });


    const backButton =
        $("#back-to-documents");

    if (backButton) {

        backButton.addEventListener(
            "click",
            () => showPage("documents")
        );

    }
}


/* ============================================================
   06. STICKY HEADER
============================================================ */

function setupStickyHeader() {

    const header =
        $("#site-header");

    if (!header) {
        return;
    }


    let ticking = false;


    function updateHeader() {

        const shouldCollapse =
            window.scrollY > 80;


        header.classList.toggle(
            "scrolled",
            shouldCollapse
        );

        header.classList.toggle(
            "is-scrolled",
            shouldCollapse
        );

        header.dataset.scrolled =
            shouldCollapse
                ? "true"
                : "false";


        ticking = false;

    }


    window.addEventListener(
        "scroll",
        () => {

            if (!ticking) {

                window.requestAnimationFrame(
                    updateHeader
                );

                ticking = true;

            }

        },
        { passive: true }
    );


    updateHeader();
}


/* ============================================================
   07. API HEALTH
============================================================ */

async function checkApiHealth() {

    const statusText =
        $("#api-status-text");

    const statusDot =
        $(".api-status-dot");

    if (!statusText) {
        return;
    }


    try {

        const data =
            await apiRequest("/health");


        if (
            data &&
            (
                data.status === "healthy" ||
                data.status === "ok"
            )
        ) {

            statusText.textContent =
                "Connected";

            if (statusDot) {

                statusDot.style.background =
                    "var(--pass-text)";

            }

        } else {

            statusText.textContent =
                "Unavailable";

            if (statusDot) {

                statusDot.style.background =
                    "var(--fail-text)";

            }

        }

    } catch (error) {

        console.error(
            "API health check failed:",
            error
        );

        statusText.textContent =
            "Offline";

        if (statusDot) {

            statusDot.style.background =
                "var(--fail-text)";

        }

    }
}


/* ============================================================
   08. DOCUMENT API NORMALIZATION
============================================================ */

function extractDocumentArray(data) {

    if (Array.isArray(data)) {
        return data;
    }

    if (!data || typeof data !== "object") {
        return [];
    }


    const possibleKeys = [
        "documents",
        "results",
        "items",
        "data"
    ];


    for (const key of possibleKeys) {

        if (Array.isArray(data[key])) {
            return data[key];
        }

    }


    return [];
}


function normalizeDocument(document) {

    if (!document || typeof document !== "object") {
        return null;
    }


    return {

        id:
            document.id ??
            null,

        document_name:
            document.document_name ??
            document.documentName ??
            document.name ??
            "Unnamed document",

        document_type:
            document.document_type ??
            document.documentType ??
            document.type ??
            "",

        status:
            normalizeStatus(
                document.status
            ),

        created_at:
            document.created_at ??
            document.createdAt ??
            document.processed_at ??
            document.processedAt ??
            null,

        updated_at:
            document.updated_at ??
            document.updatedAt ??
            null,

        file_validation:
            document.file_validation ??
            document.fileValidation ??
            {},

        extracted_data:
            document.extracted_data ??
            document.extractedData ??
            {},

        financial_validations:
            document.financial_validations ??
            document.financialValidations ??
            [],

        metadata:
            document.metadata ??
            document.document_metadata ??
            document.documentMetadata ??
            {}

    };

}


/* ============================================================
   09. LOAD DOCUMENTS
============================================================ */

async function loadDocuments() {

    try {

        const data =
            await apiRequest("/documents");


        const documents =
            extractDocumentArray(data)
                .map(normalizeDocument)
                .filter(Boolean);


        state.documents = documents;

        state.filteredDocuments =
            [...documents];


        renderDashboardStats();

        renderRecentDocuments();

        applyDocumentFilters();

    } catch (error) {

        console.error(
            "Could not load documents:",
            error
        );


        state.documents = [];

        state.filteredDocuments = [];


        renderDashboardStats();

        renderRecentDocuments();

        renderDocumentsTableError(
            error.message
        );

    }
}


/* ============================================================
   10. DASHBOARD STATISTICS
============================================================ */

function renderDashboardStats() {

    const total =
        state.documents.length;

    const passed =
        state.documents.filter(
            document =>
                document.status === "PASS"
        ).length;

    const failed =
        state.documents.filter(
            document =>
                document.status === "FAILED"
        ).length;


    const totalElement =
        $("#stat-total");

    const passedElement =
        $("#stat-passed");

    const failedElement =
        $("#stat-failed");


    if (totalElement) {
        totalElement.textContent =
            total;
    }

    if (passedElement) {
        passedElement.textContent =
            passed;
    }

    if (failedElement) {
        failedElement.textContent =
            failed;
    }
}


/* ============================================================
   11. DOCUMENT ROW
============================================================ */

function createDocumentRow(document) {

    const status =
        normalizeStatus(
            document.status
        );


    const statusClass =
        status === "PASS"
            ? "status-pass"
            : status === "FAILED"
                ? "status-failed"
                : "";


    return `
        <tr>

            <td>
                <strong class="document-name-cell">
                    ${escapeHtml(document.document_name)}
                </strong>
            </td>

            <td>
                ${escapeHtml(
                    humanizeDocumentType(
                        document.document_type
                    )
                )}
            </td>

            <td>
                <span
                    class="status-badge ${statusClass}"
                >
                    ${escapeHtml(status)}
                </span>
            </td>

            <td>
                ${formatDate(
                    document.created_at
                )}
            </td>

            <td>

                <button
                    type="button"
                    class="table-action-button"
                    data-document-name="${escapeHtml(
                        document.document_name
                    )}"
                >
                    Open →
                </button>

            </td>

        </tr>
    `;
}


/* ============================================================
   12. ATTACH OPEN BUTTONS
============================================================ */

function attachDocumentOpenButtons() {

    $$(".table-action-button").forEach(button => {

        button.addEventListener(
            "click",
            async () => {

                const name =
                    button.dataset.documentName;

                if (name) {

                    await openDocument(
                        name
                    );

                }

            }
        );

    });
}


/* ============================================================
   13. RECENT DOCUMENTS
============================================================ */

function renderRecentDocuments() {

    const tbody =
        $("#recent-documents-table-body");

    if (!tbody) {
        return;
    }


    const recent =
        [...state.documents]
            .sort(
                (a, b) =>
                    new Date(
                        b.created_at || 0
                    ) -
                    new Date(
                        a.created_at || 0
                    )
            )
            .slice(0, 5);


    if (recent.length === 0) {

        tbody.innerHTML = `
            <tr>
                <td colspan="5">

                    <div class="empty-state">

                        <div class="empty-state-icon">
                            —
                        </div>

                        <h3>
                            No processed documents yet
                        </h3>

                        <p>
                            Upload a document to begin.
                        </p>

                    </div>

                </td>
            </tr>
        `;

        return;
    }


    tbody.innerHTML =
        recent
            .map(createDocumentRow)
            .join("");


    attachDocumentOpenButtons();
}


/* ============================================================
   14. DOCUMENT FILTERS
============================================================ */

function setupDocumentFilters() {

    const search =
        $("#document-search");

    const typeFilter =
        $("#document-type-filter");

    const statusFilter =
        $("#document-status-filter");


    if (search) {

        search.addEventListener(
            "input",
            applyDocumentFilters
        );

    }

    if (typeFilter) {

        typeFilter.addEventListener(
            "change",
            applyDocumentFilters
        );

    }

    if (statusFilter) {

        statusFilter.addEventListener(
            "change",
            applyDocumentFilters
        );

    }
}


function applyDocumentFilters() {

    const search =
        ($("#document-search")?.value || "")
            .trim()
            .toLowerCase();

    const selectedType =
        $("#document-type-filter")?.value || "";

    const selectedStatus =
        $("#document-status-filter")?.value || "";


    state.filteredDocuments =
        state.documents.filter(document => {

            const matchesSearch =
                !search ||
                document.document_name
                    .toLowerCase()
                    .includes(search);


            const matchesType =
                !selectedType ||
                document.document_type === selectedType;


            const matchesStatus =
                !selectedStatus ||
                document.status === selectedStatus;


            return (
                matchesSearch &&
                matchesType &&
                matchesStatus
            );

        });


    renderDocumentsTable();

}


/* ============================================================
   15. DOCUMENTS TABLE
============================================================ */

function renderDocumentsTable() {

    const tbody =
        $("#all-documents-table-body");

    const count =
        $("#document-count");


    if (!tbody) {
        return;
    }


    const documents =
        state.filteredDocuments;


    if (count) {

        count.textContent =
            `${documents.length} ${
                documents.length === 1
                    ? "document"
                    : "documents"
            }`;

    }


    if (documents.length === 0) {

        tbody.innerHTML = `
            <tr>
                <td colspan="5">

                    <div class="empty-state">

                        <div class="empty-state-icon">
                            —
                        </div>

                        <h3>
                            No matching documents
                        </h3>

                        <p>
                            Try changing your search or filters.
                        </p>

                    </div>

                </td>
            </tr>
        `;

        return;
    }


    tbody.innerHTML =
        documents
            .map(createDocumentRow)
            .join("");


    attachDocumentOpenButtons();
}


function renderDocumentsTableError(message) {

    const tbody =
        $("#all-documents-table-body");

    if (!tbody) {
        return;
    }


    tbody.innerHTML = `
        <tr>
            <td colspan="5">

                <div class="empty-state">

                    <div class="empty-state-icon">
                        !
                    </div>

                    <h3>
                        Could not load documents
                    </h3>

                    <p>
                        ${escapeHtml(message)}
                    </p>

                </div>

            </td>
        </tr>
    `;


    const count =
        $("#document-count");

    if (count) {
        count.textContent =
            "0 documents";
    }
}


/* ============================================================
   16. OPEN DOCUMENT
============================================================ */

async function openDocument(
    documentName
) {

    showLoading(
        "Loading document",
        "Retrieving the stored processing result..."
    );


    try {

        const encodedName =
            encodeURIComponent(
                documentName
            );


        const result =
            await apiRequest(
                `/documents/${encodedName}`
            );


        state.currentResult =
            result;


        renderResult(result);

        showPage("result");


    } catch (error) {

        console.error(
            "Could not open document:",
            error
        );


        showToast(
            "Error",
            error.message ||
                "Could not open the document.",
            "error"
        );

    } finally {

        hideLoading();

    }
}


/* ============================================================
   17. RESULT RENDERING
============================================================ */

function renderResult(result) {

    const content =
        $("#result-content");

    if (!content) {
        return;
    }


    const documentName =
        result?.document_name ??
        result?.documentName ??
        "Document";


    const documentType =
        result?.document_type ??
        result?.documentType ??
        "";


    const status =
        normalizeStatus(
            result?.status
        );


    const resultType =
        $("#result-document-type");

    const resultName =
        $("#result-document-name");

    const resultSubtitle =
        $("#result-subtitle");

    const resultStatus =
        $("#result-status");


    if (resultType) {

        resultType.textContent =
            humanizeDocumentType(
                documentType
            );

    }


    if (resultName) {

        resultName.textContent =
            documentName;

    }


    if (resultSubtitle) {

        resultSubtitle.textContent =
            status === "PASS"
                ? "Structured extraction and financial validation passed."
                : status === "FAILED"
                    ? "Processing completed with validation or processing issues."
                    : "Structured extraction and financial validation.";

    }


    if (resultStatus) {

        resultStatus.textContent =
            status;

        resultStatus.className =
            "status-badge " +
            (
                status === "PASS"
                    ? "status-pass"
                    : status === "FAILED"
                        ? "status-failed"
                        : ""
            );

    }


    content.innerHTML = "";


    /* Extracted information */

    content.appendChild(
        createResultSection(
            "Extracted Information",
            renderExtractedInformation(
                result?.extracted_data ??
                result?.extractedData ??
                {}
            )
        )
    );


    /* Line items */

    const lineItems =
        findLineItems(
            result?.extracted_data ??
            result?.extractedData ??
            {}
        );


    if (lineItems.length > 0) {

        content.appendChild(
            createResultSection(
                "Line Items",
                renderLineItems(lineItems)
            )
        );

    }


    /* Structured tables */

    const tables =
        findStructuredTables(
            result?.extracted_data ??
            result?.extractedData ??
            {}
        );


    if (tables.length > 0) {

        content.appendChild(
            createResultSection(
                "Structured Tables",
                renderStructuredTables(tables),
                "plain-heading"
            )
        );

    }


    /* Financial validation */

    const validations =
        result?.financial_validations ??
        result?.financialValidations ??
        [];


    content.appendChild(
        createResultSection(
            "Financial Validation",
            renderFinancialValidation(
                validations
            )
        )
    );


    /* File validation */

    const fileValidation =
        result?.file_validation ??
        result?.fileValidation ??
        {};


    content.appendChild(
        createResultSection(
            "File Validation",
            renderFileValidation(
                fileValidation
            )
        )
    );


    /* Metadata */

    const metadata =
        result?.metadata ??
        result?.document_metadata ??
        result?.documentMetadata ??
        {};


    content.appendChild(
        createResultSection(
            "Processing Metadata",
            renderMetadata(metadata)
        )
    );


    renderRawJson(result);

}


/* ============================================================
   18. RESULT SECTION CREATOR
============================================================ */

function createResultSection(
    title,
    bodyHtml,
    extraClass = ""
) {

    const section =
        document.createElement("section");


    section.className =
        `result-section ${extraClass}`;


    section.innerHTML = `
        <div class="result-section-header">

            <h2>
                ${escapeHtml(title)}
            </h2>

        </div>

        <div class="result-section-body">
            ${bodyHtml}
        </div>
    `;


    return section;
}


/* ============================================================
   19. EXTRACTED DATA NORMALIZATION
============================================================ */

function flattenExtractedData(
    data,
    prefix = ""
) {

    const rows = [];


    if (!isObject(data)) {
        return rows;
    }


    for (const [key, value] of Object.entries(data)) {

        const fieldName =
            prefix
                ? `${prefix}.${key}`
                : key;


        /* Evidence object */

        if (
            isObject(value) &&
            (
                "value" in value ||
                "source_text" in value ||
                "sourceText" in value ||
                "page_number" in value ||
                "pageNumber" in value ||
                "confidence" in value
            )
        ) {

            const extractedValue =
                value.value ??
                value.extracted_value ??
                value.extractedValue ??
                null;


            rows.push({

                field: fieldName,

                value: extractedValue,

                evidence:
                    value.source_text ??
                    value.sourceText ??
                    value.evidence ??
                    "—",

                page:
                    value.page_number ??
                    value.pageNumber ??
                    "—",

                confidence:
                    value.confidence ??
                    "—"

            });


            continue;
        }


        /* Arrays are handled separately */

        if (Array.isArray(value)) {

            if (
                value.length > 0 &&
                value.every(
                    item =>
                        isObject(item)
                )
            ) {

                continue;

            }


            rows.push({

                field: fieldName,

                value: value.join(", "),

                evidence: "—",

                page: "—",

                confidence: "—"

            });


            continue;
        }


        /* Nested object */

        if (isObject(value)) {

            rows.push(
                ...flattenExtractedData(
                    value,
                    fieldName
                )
            );

            continue;
        }


        rows.push({

            field: fieldName,

            value,

            evidence: "—",

            page: "—",

            confidence: "—"

        });

    }


    return rows;
}


/* ============================================================
   20. EXTRACTED INFORMATION TABLE
============================================================ */

function renderExtractedInformation(
    data
) {

    const rows =
        flattenExtractedData(data);


    if (rows.length === 0) {

        return `
            <div class="empty-state">

                <div class="empty-state-icon">
                    —
                </div>

                <h3>
                    No extracted information
                </h3>

                <p>
                    No structured fields were returned.
                </p>

            </div>
        `;

    }


    const body =
        rows.map(row => {

            const valueHtml =
                isEmptyValue(row.value)
                    ? `<span class="missing-value">
                           Not available
                       </span>`
                    : formatValue(row.value);


            return `
                <tr>

                    <td class="extraction-field">
                        ${escapeHtml(
                            humanizeKey(row.field)
                        )}
                    </td>

                    <td>
                        ${valueHtml}
                    </td>

                    <td>
                        ${
                            isEmptyValue(
                                row.evidence
                            )
                                ? `<span class="missing-value">
                                       Not available
                                   </span>`
                                : escapeHtml(
                                    row.evidence
                                )
                        }
                    </td>

                    <td>
                        ${escapeHtml(
                            row.page ?? "—"
                        )}
                    </td>

                    <td>
                        ${formatConfidence(
                            row.confidence
                        )}
                    </td>

                </tr>
            `;

        }).join("");


    return `
        <div class="extraction-table-wrapper">

            <table class="extraction-table">

                <thead>

                    <tr>

                        <th>
                            Field
                        </th>

                        <th>
                            Extracted Value
                        </th>

                        <th>
                            Evidence
                        </th>

                        <th>
                            Page
                        </th>

                        <th>
                            Confidence
                        </th>

                    </tr>

                </thead>

                <tbody>
                    ${body}
                </tbody>

            </table>

        </div>
    `;
}


function formatConfidence(
    confidence
) {

    if (
        confidence === null ||
        confidence === undefined ||
        confidence === ""
    ) {

        return "—";

    }


    if (
        typeof confidence === "number"
    ) {

        const percentage =
            confidence <= 1
                ? confidence * 100
                : confidence;

        return `${percentage.toFixed(0)}%`;

    }


    return escapeHtml(
        confidence
    );
}


/* ============================================================
   21. FIND LINE ITEMS
============================================================ */

function findLineItems(data) {

    if (!isObject(data)) {
        return [];
    }


    const possibleKeys = [
        "line_items",
        "lineItems",
        "items",
        "invoice_items",
        "invoiceItems"
    ];


    for (const key of possibleKeys) {

        if (Array.isArray(data[key])) {

            return data[key];

        }

    }


    return [];
}


/* ============================================================
   22. LINE ITEMS TABLE
============================================================ */

function renderLineItems(
    items
) {

    if (!Array.isArray(items) || items.length === 0) {

        return `
            <div class="empty-state">
                <h3>No line items</h3>
            </div>
        `;

    }


    const allKeys =
        new Set();


    items.forEach(item => {

        if (isObject(item)) {

            Object.keys(item)
                .forEach(key =>
                    allKeys.add(key)
                );

        }

    });


    const keys =
        [...allKeys];


    const headers =
        keys
            .map(
                key =>
                    `<th>${escapeHtml(
                        humanizeKey(key)
                    )}</th>`
            )
            .join("");


    const rows =
        items.map(item => {

            const cells =
                keys.map(key => {

                    const value =
                        isObject(item)
                            ? item[key]
                            : null;


                    return `
                        <td>
                            ${formatValue(value)}
                        </td>
                    `;

                }).join("");


            return `
                <tr>
                    ${cells}
                </tr>
            `;

        }).join("");


    return `
        <div class="line-items-wrapper">

            <table class="line-items-table">

                <thead>
                    <tr>
                        ${headers}
                    </tr>
                </thead>

                <tbody>
                    ${rows}
                </tbody>

            </table>

        </div>
    `;
}


/* ============================================================
   23. STRUCTURED TABLES
============================================================ */

function findStructuredTables(data) {

    if (!isObject(data)) {
        return [];
    }


    const possibleKeys = [
        "tables",
        "structured_tables",
        "structuredTables",
        "document_tables"
    ];


    for (const key of possibleKeys) {

        if (Array.isArray(data[key])) {

            return data[key];

        }

    }


    return [];
}


function renderStructuredTables(
    tables
) {

    if (!Array.isArray(tables) || tables.length === 0) {

        return `
            <div class="empty-state">
                <h3>No structured tables</h3>
            </div>
        `;

    }


    return tables.map(
        (table, index) => {

            const title =
                table?.title ??
                table?.name ??
                `Table ${index + 1}`;


            let rows =
                table?.rows ??
                table?.data ??
                [];


            if (
                !Array.isArray(rows) &&
                isObject(rows)
            ) {

                rows = [rows];

            }


            if (
                Array.isArray(table) ||
                Array.isArray(rows)
            ) {

                const actualRows =
                    Array.isArray(table)
                        ? table
                        : rows;


                return renderSingleStructuredTable(
                    title,
                    actualRows
                );

            }


            return "";

        }
    ).join("");
}


function renderSingleStructuredTable(
    title,
    rows
) {

    if (!Array.isArray(rows) || rows.length === 0) {

        return `
            <div class="structured-table-wrapper">

                <h3>
                    ${escapeHtml(title)}
                </h3>

                <div class="empty-state">
                    No rows available.
                </div>

            </div>
        `;

    }


    const keySet =
        new Set();


    rows.forEach(row => {

        if (isObject(row)) {

            Object.keys(row)
                .forEach(
                    key => keySet.add(key)
                );

        }

    });


    const keys =
        [...keySet];


    if (keys.length === 0) {

        return "";

    }


    const headerHtml =
        keys.map(
            key =>
                `<th>${escapeHtml(
                    humanizeKey(key)
                )}</th>`
        ).join("");


    const bodyHtml =
        rows.map(row => {

            const cells =
                keys.map(key => {

                    const value =
                        isObject(row)
                            ? row[key]
                            : null;


                    return `
                        <td>
                            ${formatValue(value)}
                        </td>
                    `;

                }).join("");


            return `
                <tr>
                    ${cells}
                </tr>
            `;

        }).join("");


    return `
        <div class="structured-table-wrapper">

            <h3
                style="
                    padding: 18px 18px 8px;
                    margin: 0;
                    color: var(--maroon);
                    font-family: Manrope, sans-serif;
                    font-size: 16px;
                "
            >
                ${escapeHtml(title)}
            </h3>

            <table class="structured-data-table">

                <thead>
                    <tr>
                        ${headerHtml}
                    </tr>
                </thead>

                <tbody>
                    ${bodyHtml}
                </tbody>

            </table>

        </div>
    `;
}


/* ============================================================
   24. FINANCIAL VALIDATION
============================================================ */

function renderFinancialValidation(
    validations
) {

    if (
        !Array.isArray(validations) ||
        validations.length === 0
    ) {

        return `
            <div class="empty-state">

                <div class="empty-state-icon">
                    —
                </div>

                <h3>
                    No validation checks
                </h3>

                <p>
                    No applicable financial validation was returned.
                </p>

            </div>
        `;

    }


    const html =
        validations.map(validation => {

            const status =
                String(
                    validation?.status ??
                    "NOT_APPLICABLE"
                ).toUpperCase();


            const statusClass =
                status === "PASS"
                    ? "pass"
                    : status === "FAIL"
                        ? "fail"
                        : "not-applicable";


            const check =
                validation?.check ??
                "Financial validation";


            return `
                <div
                    class="validation-item ${statusClass}"
                >

                    <div class="validation-top">

                        <div class="validation-check">
                            ${escapeHtml(check)}
                        </div>

                        <span
                            class="validation-status ${statusClass}"
                        >
                            ${escapeHtml(status)}
                        </span>

                    </div>


                    <div class="validation-details">

                        ${renderValidationDetail(
                            "Input Values",
                            validation?.input_values ??
                            validation?.inputValues
                        )}

                        ${renderValidationDetail(
                            "Calculated",
                            validation?.calculated_value ??
                            validation?.calculated
                        )}

                        ${renderValidationDetail(
                            "Reported",
                            validation?.reported_value ??
                            validation?.reported
                        )}

                        ${renderValidationDetail(
                            "Variance",
                            validation?.variance
                        )}

                    </div>

                </div>
            `;

        }).join("");


    return `
        <div class="validation-list">
            ${html}
        </div>
    `;
}


function renderValidationDetail(
    label,
    value
) {

    return `
        <div class="validation-detail">

            <span class="validation-detail-label">
                ${escapeHtml(label)}
            </span>

            <span class="validation-detail-value">
                ${
                    isEmptyValue(value)
                        ? "—"
                        : formatValue(value)
                }
            </span>

        </div>
    `;
}


/* ============================================================
   25. FILE VALIDATION
============================================================ */

function renderFileValidation(
    validation
) {

    if (
        !isObject(validation) ||
        Object.keys(validation).length === 0
    ) {

        return `
            <div class="empty-state">
                <h3>
                    No file validation details
                </h3>
            </div>
        `;

    }


    return renderInfoGrid(
        validation
    );
}


/* ============================================================
   26. METADATA
============================================================ */

function renderMetadata(
    metadata
) {

    if (
        !isObject(metadata) ||
        Object.keys(metadata).length === 0
    ) {

        return `
            <div class="empty-state">
                <h3>
                    No metadata available
                </h3>
            </div>
        `;

    }


    return renderInfoGrid(
        metadata
    );
}


/* ============================================================
   27. INFO GRID
============================================================ */

function renderInfoGrid(
    data
) {

    const rows =
        Object.entries(data)
            .map(([key, value]) => {

                return `
                    <div class="info-row">

                        <span class="info-label">
                            ${escapeHtml(
                                humanizeKey(key)
                            )}
                        </span>

                        <span class="info-value">
                            ${formatValue(value)}
                        </span>

                    </div>
                `;

            })
            .join("");


    return `
        <div class="info-grid">
            ${rows}
        </div>
    `;
}


/* ============================================================
   28. RAW JSON
============================================================ */

function renderRawJson(
    result
) {

    const rawSection =
        $("#raw-json-section");

    const rawContent =
        $("#raw-json-content");

    if (!rawSection || !rawContent) {
        return;
    }


    rawSection.hidden = true;


    rawContent.textContent =
        JSON.stringify(
            result,
            null,
            2
        );


    const toggle =
        $("#toggle-raw-json");


    if (toggle) {

        toggle.textContent =
            "View raw JSON";

    }
}


function setupRawJson() {

    const toggle =
        $("#toggle-raw-json");

    const rawSection =
        $("#raw-json-section");

    const copyButton =
        $("#copy-json-button");

    if (!toggle || !rawSection) {
        return;
    }


    toggle.addEventListener(
        "click",
        () => {

            const isHidden =
                rawSection.hidden;


            rawSection.hidden =
                !isHidden;


            toggle.textContent =
                isHidden
                    ? "Hide raw JSON"
                    : "View raw JSON";


            if (isHidden) {

                setTimeout(
                    () => {

                        rawSection.scrollIntoView({
                            behavior: "smooth",
                            block: "start"
                        });

                    },
                    50
                );

            }

        }
    );


    if (copyButton) {

        copyButton.addEventListener(
            "click",
            async () => {

                if (!state.currentResult) {
                    return;
                }


                try {

                    await navigator.clipboard.writeText(
                        JSON.stringify(
                            state.currentResult,
                            null,
                            2
                        )
                    );


                    showToast(
                        "Copied",
                        "Raw JSON copied to clipboard.",
                        "success"
                    );

                } catch (error) {

                    console.error(
                        "Copy failed:",
                        error
                    );


                    showToast(
                        "Copy failed",
                        "The JSON could not be copied.",
                        "error"
                    );

                }

            }
        );

    }
}


/* ============================================================
   29. UPLOAD
============================================================ */

function setupUpload() {

    const fileInput =
        $("#file-input");

    const dropZone =
        $("#drop-zone");

    const browseButton =
        $("#browse-button");

    const removeButton =
        $("#remove-file");

    const processButton =
        $("#process-button");


    if (!fileInput || !dropZone) {
        return;
    }


    if (browseButton) {

        browseButton.addEventListener(
            "click",
            event => {

                event.stopPropagation();

                fileInput.click();

            }
        );

    }


    dropZone.addEventListener(
        "click",
        event => {

            if (
                event.target === browseButton
            ) {
                return;
            }

            fileInput.click();

        }
    );


    dropZone.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Enter" ||
                event.key === " "
            ) {

                event.preventDefault();

                fileInput.click();

            }

        }
    );


    fileInput.addEventListener(
        "change",
        event => {

            const file =
                event.target.files?.[0];

            if (file) {

                handleSelectedFile(file);

            }

        }
    );


    /* Drag & drop */

    [
        "dragenter",
        "dragover"
    ].forEach(eventName => {

        dropZone.addEventListener(
            eventName,
            event => {

                event.preventDefault();

                dropZone.classList.add(
                    "dragover"
                );

            }
        );

    });


    [
        "dragleave",
        "drop"
    ].forEach(eventName => {

        dropZone.addEventListener(
            eventName,
            event => {

                event.preventDefault();

                dropZone.classList.remove(
                    "dragover"
                );

            }
        );

    });


    dropZone.addEventListener(
        "drop",
        event => {

            const file =
                event.dataTransfer.files?.[0];

            if (file) {

                handleSelectedFile(file);

            }

        }
    );


    if (removeButton) {

        removeButton.addEventListener(
            "click",
            clearSelectedFile
        );

    }


    if (processButton) {

        processButton.addEventListener(
            "click",
            processDocument
        );

    }

}


function handleSelectedFile(
    file
) {

    const validation =
        validateBrowserFile(file);


    if (!validation.valid) {

        showUploadMessage(
            validation.message,
            "error"
        );

        clearSelectedFile();

        return;
    }


    state.selectedFile =
        file;


    const selectedFile =
        $("#selected-file");

    const fileName =
        $("#file-name");

    const fileSize =
        $("#file-size");

    const processButton =
        $("#process-button");


    if (selectedFile) {
        selectedFile.hidden = false;
    }

    if (fileName) {
        fileName.textContent =
            file.name;
    }

    if (fileSize) {
        fileSize.textContent =
            formatFileSize(file.size);
    }

    if (processButton) {
        processButton.disabled = false;
    }


    showUploadMessage(
        "File ready for processing.",
        "success"
    );
}


function validateBrowserFile(
    file
) {

    if (!file) {

        return {
            valid: false,
            message: "Please select a file."
        };

    }


    if (file.size <= 0) {

        return {
            valid: false,
            message: "The selected file is empty."
        };

    }


    if (file.size > MAX_FILE_SIZE) {

        return {
            valid: false,
            message:
                "File exceeds the 10 MB size limit."
        };

    }


    const fileName =
        file.name.toLowerCase();


    const extension =
        ALLOWED_EXTENSIONS.find(
            ext =>
                fileName.endsWith(ext)
        );


    if (!extension) {

        return {
            valid: false,
            message:
                "Unsupported file type. Use PDF, JPG or PNG."
        };

    }


    if (
        file.type &&
        !ALLOWED_MIME_TYPES.includes(
            file.type
        )
    ) {

        return {
            valid: false,
            message:
                "The selected file format is not supported."
        };

    }


    return {
        valid: true
    };
}


function clearSelectedFile() {

    state.selectedFile =
        null;


    const fileInput =
        $("#file-input");

    const selectedFile =
        $("#selected-file");

    const processButton =
        $("#process-button");


    if (fileInput) {
        fileInput.value = "";
    }

    if (selectedFile) {
        selectedFile.hidden = true;
    }

    if (processButton) {
        processButton.disabled = true;
    }


    showUploadMessage(
        "",
        ""
    );
}


function formatFileSize(
    bytes
) {

    if (bytes < 1024) {
        return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
        return `${(
            bytes / 1024
        ).toFixed(1)} KB`;
    }

    return `${(
        bytes /
        (1024 * 1024)
    ).toFixed(2)} MB`;
}


/* ============================================================
   30. UPLOAD MESSAGE
============================================================ */

function showUploadMessage(
    message,
    type = ""
) {

    const element =
        $("#upload-message");

    if (!element) {
        return;
    }


    element.textContent =
        message || "";


    element.className =
        "upload-message";


    if (type) {
        element.classList.add(type);
    }
}


/* ============================================================
   31. PROCESS DOCUMENT
============================================================ */

async function processDocument() {

    if (state.isProcessing) {
        return;
    }


    const documentType =
        $("#document-type")?.value || "";


    if (!documentType) {

        showUploadMessage(
            "Please select a document type.",
            "error"
        );

        return;
    }


    if (!state.selectedFile) {

        showUploadMessage(
            "Please select a document to process.",
            "error"
        );

        return;
    }


    state.isProcessing =
        true;


    const processButton =
        $("#process-button");


    if (processButton) {

        processButton.disabled =
            true;

        processButton.innerHTML =
            "Processing... <span>→</span>";

    }


    showLoading(
        "Processing document",
        "Extracting, validating and storing..."
    );


    try {

        const formData =
            new FormData();


        formData.append(
            "file",
            state.selectedFile
        );


        formData.append(
            "document_type",
            documentType
        );


        const response =
            await fetch(
                `${API_BASE}/documents/process`,
                {
                    method: "POST",
                    body: formData
                }
            );


        let data = null;


        try {

            data =
                await response.json();

        } catch {

            data = null;

        }


        if (!response.ok) {

            const errorMessage =
                data?.error?.message ||
                data?.detail?.error?.message ||
                data?.detail ||
                "The document could not be processed.";


            throw new Error(
                errorMessage
            );

        }


        state.currentResult =
            data;


        /* Refresh document list */

        await loadDocuments();


        /* Show result */

        renderResult(data);

        showPage("result");


        showToast(
            "Success",
            "Document processed successfully.",
            "success"
        );


        /* Clear upload state */

        clearSelectedFile();


        const typeSelect =
            $("#document-type");

        if (typeSelect) {
            typeSelect.value = "";
        }


    } catch (error) {

        console.error(
            "Document processing failed:",
            error
        );


        showUploadMessage(
            error.message ||
                "The document could not be processed.",
            "error"
        );


        showToast(
            "Processing failed",
            error.message ||
                "The document could not be processed.",
            "error"
        );


    } finally {

        /*
           CRITICAL:
           Always hide the loading overlay,
           whether processing succeeds or fails.
        */

        hideLoading();


        state.isProcessing =
            false;


        if (processButton) {

            processButton.disabled =
                !state.selectedFile;

            processButton.innerHTML =
                "Process document <span>→</span>";

        }

    }
}


/* ============================================================
   32. LOADING OVERLAY
============================================================ */

function showLoading(
    title = "Processing document",
    message = "Please wait..."
) {

    const overlay =
        $("#loading-overlay");

    if (!overlay) {
        return;
    }


    const strong =
        overlay.querySelector(
            ".loading-panel strong"
        );

    const messageElement =
        overlay.querySelector(
            ".loading-panel > span"
        );


    if (strong) {
        strong.textContent =
            title;
    }

    if (messageElement) {
        messageElement.textContent =
            message;
    }


    overlay.hidden =
        false;

    overlay.setAttribute(
        "aria-hidden",
        "false"
    );

}


function hideLoading() {

    const overlay =
        $("#loading-overlay");

    if (!overlay) {
        return;
    }


    overlay.hidden =
        true;

    overlay.setAttribute(
        "aria-hidden",
        "true"
    );

}


/* ============================================================
   33. TOAST
============================================================ */

let toastTimer = null;


function showToast(
    title,
    message,
    type = "success"
) {

    const toast =
        $("#toast");

    const icon =
        $("#toast-icon");

    const titleElement =
        $("#toast-title");

    const messageElement =
        $("#toast-message");


    if (
        !toast ||
        !icon ||
        !titleElement ||
        !messageElement
    ) {
        return;
    }


    clearTimeout(
        toastTimer
    );


    titleElement.textContent =
        title;


    messageElement.textContent =
        message;


    if (type === "error") {

        icon.textContent =
            "!";

        icon.style.color =
            "var(--fail-text)";

        icon.style.background =
            "var(--fail-bg)";

    } else {

        icon.textContent =
            "✓";

        icon.style.color =
            "var(--pass-text)";

        icon.style.background =
            "var(--pass-bg)";

    }


    toast.hidden =
        false;


    toastTimer =
        setTimeout(
            () => {

                toast.hidden =
                    true;

            },
            5000
        );

}


function setupToast() {

    const closeButton =
        $("#toast-close");

    if (!closeButton) {
        return;
    }


    closeButton.addEventListener(
        "click",
        () => {

            const toast =
                $("#toast");

            if (toast) {
                toast.hidden = true;
            }

            clearTimeout(
                toastTimer
            );

        }
    );
}


/* ============================================================
   34. DOCUMENT TYPE RESET
============================================================ */

function setupUploadPageReset() {

    $$(".nav-button").forEach(button => {

        button.addEventListener(
            "click",
            () => {

                if (
                    button.dataset.page ===
                    "upload"
                ) {

                    /*
                       Keep selected file if user
                       intentionally returns to upload.
                       Do not automatically destroy state.
                    */

                }

            }
        );

    });
}


/* ============================================================
   35. KEYBOARD ESCAPE
============================================================ */

function setupKeyboardShortcuts() {

    document.addEventListener(
        "keydown",
        event => {

            if (
                event.key === "Escape"
            ) {

                const loading =
                    $("#loading-overlay");

                if (
                    loading &&
                    !loading.hidden
                ) {

                    /*
                       Do not allow Escape to cancel
                       an active backend process.
                    */

                }

                const rawSection =
                    $("#raw-json-section");

                if (
                    rawSection &&
                    !rawSection.hidden
                ) {

                    rawSection.hidden =
                        true;

                    const toggle =
                        $("#toggle-raw-json");

                    if (toggle) {

                        toggle.textContent =
                            "View raw JSON";

                    }

                }

            }

        }
    );
}


/* ============================================================
   36. INITIALIZATION
============================================================ */

async function initializeApp() {

    console.log(
        "CREDORA application initializing..."
    );


    setupNavigation();

    setupStickyHeader();

    setupDocumentFilters();

    setupUpload();

    setupRawJson();

    setupToast();

    setupUploadPageReset();

    setupKeyboardShortcuts();


    /*
       Make absolutely sure the overlay starts hidden.
    */

    hideLoading();


    /*
       Check API and load stored documents.
    */

    await Promise.all([
        checkApiHealth(),
        loadDocuments()
    ]);


    /*
       Start on dashboard.
    */

    showPage("dashboard");


    console.log(
        "CREDORA application ready."
    );

}


/* ============================================================
   37. START APPLICATION
============================================================ */

if (
    document.readyState === "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeApp
    );

} else {

    initializeApp();

}
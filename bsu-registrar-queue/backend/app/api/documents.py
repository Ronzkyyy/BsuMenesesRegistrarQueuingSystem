"""
Document catalog endpoints - what students can request under Request Documents
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from ..core.audit import log_security_event
from ..core.database import get_db
from ..core.limiter import limiter
from ..core.security import require_role
from ..db_models import UserRole
from ..models.document import Document, DocumentCreate, DocumentOrder, DocumentPublic, DocumentUpdate
from ..models.user import User
from ..services.document_service import DocumentService


router = APIRouter()


@router.get("/active", response_model=List[DocumentPublic])
@limiter.limit("30/minute")
def list_active_documents(request: Request, db: Session = Depends(get_db)):
    """Active documents in display order, for the kiosk and booking form (public endpoint)"""
    return DocumentService(db).list_active()


@router.get("", response_model=List[Document])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Full catalog, including inactive entries (admin only)"""
    return DocumentService(db).list_all()


@router.post("", response_model=Document, status_code=201)
def create_document(
    request: Request,
    data: DocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Add a document to the catalog (admin only)"""
    try:
        document = DocumentService(db).create(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_security_event(
        "document.created", outcome="success", request=request,
        actor=current_user.username, target=f"document#{document.id}",
    )
    return document


# Declared before /{document_id} so "order" is never parsed as an id.
@router.put("/order", response_model=List[Document])
def reorder_documents(
    request: Request,
    data: DocumentOrder,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Save a new display order - must list every document once (admin only)"""
    try:
        documents = DocumentService(db).reorder(data.document_ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_security_event(
        "document.reordered", outcome="success", request=request,
        actor=current_user.username,
    )
    return documents


@router.patch("/{document_id}", response_model=Document)
def update_document(
    request: Request,
    data: DocumentUpdate,
    document_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """Edit a document, or (de)activate it with is_active (admin only)"""
    try:
        document, changed = DocumentService(db).update(document_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    target = f"document#{document.id}"
    if "is_active" in changed:
        log_security_event(
            "document.activated" if document.is_active else "document.deactivated",
            outcome="success", request=request, actor=current_user.username, target=target,
        )
    edited = [field for field in changed if field != "is_active"]
    if edited:
        # Names the fields only - a fee change is what students rely on.
        log_security_event(
            "document.updated", outcome="success", request=request,
            actor=current_user.username, target=target, detail=", ".join(edited),
        )
    return document

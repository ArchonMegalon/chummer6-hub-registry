using Chummer.Hub.Registry.Contracts;
using Chummer.Run.Registry.Services;
using Microsoft.AspNetCore.Mvc;

namespace Chummer.Run.Registry.Controllers;

[ApiController]
[Route("api/v1/publication-drafts")]
public sealed class HubPublicationDraftsController : ControllerBase
{
    private readonly IHubPublicationDraftService _drafts;

    public HubPublicationDraftsController(IHubPublicationDraftService drafts)
    {
        _drafts = drafts;
    }

    [HttpGet]
    [ProducesResponseType<HubPublishDraftList>(StatusCodes.Status200OK)]
    public ActionResult<HubPublishDraftList> ListDrafts(
        [FromQuery] string? ownerId = null,
        [FromQuery] string? state = null,
        [FromQuery] string? projectId = null)
        => Ok(_drafts.ListDrafts(ownerId, state, projectId));

    [HttpPost]
    [ProducesResponseType<HubPublishDraftReceipt>(StatusCodes.Status201Created)]
    public ActionResult<HubPublishDraftReceipt> CreateDraft(
        [FromBody] HubPublishDraftRequest? request,
        [FromQuery] string ownerId,
        [FromQuery] string? preferredDraftId = null)
    {
        if (request is null)
        {
            return BadRequest("Draft payload is required.");
        }

        try
        {
            HubPublishDraftReceipt created = _drafts.CreateDraft(request, ownerId, preferredDraftId);
            return CreatedAtAction(nameof(GetDraftDetail), new { draftId = created.DraftId }, created);
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
    }

    [HttpGet("moderation")]
    [ProducesResponseType<HubModerationQueue>(StatusCodes.Status200OK)]
    public ActionResult<HubModerationQueue> ListModerationQueue(
        [FromQuery] string? ownerId = null,
        [FromQuery] string? publisherId = null,
        [FromQuery] string? state = null)
        => Ok(_drafts.ListModerationQueue(ownerId, publisherId, state));

    [HttpPost("moderation/{caseId}/approve")]
    [ProducesResponseType<HubModerationDecisionReceipt>(StatusCodes.Status200OK)]
    public ActionResult<HubModerationDecisionReceipt> ApproveModerationCase(
        [FromRoute] string caseId,
        [FromBody] HubModerationDecisionRequest? request,
        [FromQuery] string actorId)
        => FromDecision(() => _drafts.ApproveModerationCase(caseId, actorId, request ?? new HubModerationDecisionRequest()));

    [HttpPost("moderation/{caseId}/reject")]
    [ProducesResponseType<HubModerationDecisionReceipt>(StatusCodes.Status200OK)]
    public ActionResult<HubModerationDecisionReceipt> RejectModerationCase(
        [FromRoute] string caseId,
        [FromBody] HubModerationDecisionRequest? request,
        [FromQuery] string actorId)
        => FromDecision(() => _drafts.RejectModerationCase(caseId, actorId, request ?? new HubModerationDecisionRequest()));

    [HttpGet("{draftId}")]
    [ProducesResponseType<HubDraftDetailProjection>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubDraftDetailProjection> GetDraftDetail([FromRoute] string draftId)
    {
        HubDraftDetailProjection? detail = _drafts.GetDraftDetail(draftId);
        return detail is null ? NotFound() : Ok(detail);
    }

    [HttpPut("{draftId}")]
    [ProducesResponseType<HubPublishDraftReceipt>(StatusCodes.Status200OK)]
    public ActionResult<HubPublishDraftReceipt> UpdateDraft(
        [FromRoute] string draftId,
        [FromBody] HubUpdateDraftRequest? request,
        [FromQuery] string ownerId)
    {
        if (request is null)
        {
            return BadRequest("Draft update payload is required.");
        }

        try
        {
            return Ok(_drafts.UpdateDraft(draftId, ownerId, request));
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, detail: ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, detail: ex.Message);
        }
    }

    [HttpPost("{draftId}/archive")]
    [ProducesResponseType<HubPublishDraftReceipt>(StatusCodes.Status200OK)]
    public ActionResult<HubPublishDraftReceipt> ArchiveDraft([FromRoute] string draftId, [FromQuery] string ownerId)
    {
        try
        {
            return Ok(_drafts.ArchiveDraft(draftId, ownerId));
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, detail: ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, detail: ex.Message);
        }
    }

    [HttpDelete("{draftId}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public IActionResult DeleteDraft([FromRoute] string draftId, [FromQuery] string ownerId)
    {
        try
        {
            return _drafts.DeleteDraft(draftId, ownerId) ? NoContent() : NotFound();
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, detail: ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, detail: ex.Message);
        }
    }

    [HttpPost("{draftId}/submit")]
    [ProducesResponseType<HubProjectSubmissionReceipt>(StatusCodes.Status200OK)]
    public ActionResult<HubProjectSubmissionReceipt> SubmitProject(
        [FromRoute] string draftId,
        [FromBody] HubSubmitProjectRequest? request,
        [FromQuery] string ownerId)
    {
        try
        {
            return Ok(_drafts.SubmitProject(draftId, ownerId, request ?? new HubSubmitProjectRequest()));
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, detail: ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, detail: ex.Message);
        }
    }

    [HttpPost("{draftId}/publish")]
    [ProducesResponseType<HubPublicationReceipt>(StatusCodes.Status200OK)]
    public ActionResult<HubPublicationReceipt> PublishProject(
        [FromRoute] string draftId,
        [FromBody] HubPublishProjectRequest? request,
        [FromQuery] string actorId)
    {
        try
        {
            return Ok(_drafts.PublishProject(draftId, actorId, request ?? new HubPublishProjectRequest()));
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, detail: ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, detail: ex.Message);
        }
    }

    [HttpGet("{draftId}/receipt")]
    [ProducesResponseType<HubPublicationReceipt>(StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public ActionResult<HubPublicationReceipt> GetPublicationReceipt([FromRoute] string draftId)
    {
        HubPublicationReceipt? receipt = _drafts.GetPublicationReceipt(draftId);
        return receipt is null ? NotFound() : Ok(receipt);
    }

    private ActionResult<HubModerationDecisionReceipt> FromDecision(Func<HubModerationDecisionReceipt> operation)
    {
        try
        {
            return Ok(operation());
        }
        catch (ArgumentException ex)
        {
            return Problem(statusCode: StatusCodes.Status400BadRequest, detail: ex.Message);
        }
        catch (KeyNotFoundException ex)
        {
            return Problem(statusCode: StatusCodes.Status404NotFound, detail: ex.Message);
        }
        catch (InvalidOperationException ex)
        {
            return Problem(statusCode: StatusCodes.Status409Conflict, detail: ex.Message);
        }
    }
}

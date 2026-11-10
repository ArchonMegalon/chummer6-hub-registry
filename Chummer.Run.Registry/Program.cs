using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Chummer.Run.Registry.Services;

var builder = WebApplication.CreateBuilder(args);
RegistryAuthorization.ValidateStartupConfiguration(builder.Configuration);
bool enableHttpsRedirection =
    builder.Configuration.GetValue<bool>("CHUMMER_REGISTRY_ENABLE_HTTPS_REDIRECTION");

// Add services to the container.

builder.Services.AddProblemDetails();
builder.Services
    .AddControllers()
    .ConfigureApiBehaviorOptions(options =>
    {
        options.InvalidModelStateResponseFactory = context =>
        {
            var problem = new ValidationProblemDetails(context.ModelState)
            {
                Title = "Request validation failed.",
                Type = "https://chummer.run/problems/validation",
                Status = StatusCodes.Status400BadRequest
            };

            return new BadRequestObjectResult(problem);
        };
    });
builder.Services.AddRegistryDurableState();
builder.Services.AddSingleton<IReleaseChannelManifestStore, FileReleaseChannelManifestStore>();
builder.Services
    .AddAuthentication(RegistryAuthorization.Scheme)
    .AddScheme<AuthenticationSchemeOptions, RegistryControlApiKeyAuthenticationHandler>(
        RegistryAuthorization.Scheme,
        _ => { });
builder.Services.AddAuthorization(options =>
{
    var controlPolicy = new AuthorizationPolicyBuilder(RegistryAuthorization.Scheme)
        .RequireAuthenticatedUser()
        .RequireClaim("scope", RegistryAuthorization.ControlPolicy)
        .Build();

    options.DefaultPolicy = controlPolicy;
    options.FallbackPolicy = controlPolicy;
    options.AddPolicy(RegistryAuthorization.ControlPolicy, controlPolicy);
});

var app = builder.Build();
// Fail startup on corrupt/unsupported state, before health or routes can report readiness.
app.Services.GetRequiredService<IHubArtifactStore>();
app.Services.GetRequiredService<IHubPublicationDraftService>();
app.Services.GetRequiredService<IPublicationWorkflowService>();

// Configure the HTTP request pipeline.

app.UseExceptionHandler();
if (enableHttpsRedirection)
{
    app.UseHttpsRedirection();
}

app.UseAuthentication();
app.UseAuthorization();

app.MapGet(
        "/health",
        () => Results.Ok(new
        {
            service = "chummer-run-registry",
            status = "healthy"
        }))
    .AllowAnonymous();
app.MapControllers();

app.Run();

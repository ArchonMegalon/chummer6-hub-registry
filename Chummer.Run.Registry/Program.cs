using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Chummer.Run.Registry.Services;

var builder = WebApplication.CreateBuilder(args);

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
builder.Services.AddSingleton<IPublicationWorkflowService, PublicationWorkflowService>();
builder.Services.AddSingleton<IHubPublicationDraftService, HubPublicationDraftService>();
builder.Services.AddSingleton<IHubArtifactStore, FileBackedHubArtifactStore>();
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

// Configure the HTTP request pipeline.

app.UseExceptionHandler();
app.UseHttpsRedirection();

app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

app.Run();

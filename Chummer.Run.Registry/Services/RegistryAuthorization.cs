using System.Security.Claims;
using System.Security.Cryptography;
using System.Text;
using System.Text.Encodings.Web;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Options;

namespace Chummer.Run.Registry.Services;

public static class RegistryAuthorization
{
    public const string Scheme = "RegistryControlApiKey";
    public const string ControlPolicy = "registry.control";
    public const string HeaderName = "X-Chummer-Registry-Key";
    public const string PrimaryApiKeyConfigKey = "CHUMMER_REGISTRY_CONTROL_API_KEY";
    public const string LegacyApiKeyConfigKey = "REGISTRY_CONTROL_API_KEY";

    public static void ValidateStartupConfiguration(IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(configuration);
        if (string.IsNullOrWhiteSpace(GetConfiguredControlCredential(configuration)))
        {
            throw new InvalidOperationException(
                $"Registry startup requires {PrimaryApiKeyConfigKey} (or the legacy {LegacyApiKeyConfigKey} compatibility key) to be configured.");
        }
    }

    public static string? GetConfiguredControlCredential(IConfiguration configuration)
    {
        ArgumentNullException.ThrowIfNull(configuration);
        string? primary = configuration[PrimaryApiKeyConfigKey]?.Trim();
        return !string.IsNullOrWhiteSpace(primary)
            ? primary
            : configuration[LegacyApiKeyConfigKey]?.Trim();
    }
}

public sealed class RegistryControlApiKeyAuthenticationHandler : AuthenticationHandler<AuthenticationSchemeOptions>
{
    private readonly IConfiguration _configuration;

    public RegistryControlApiKeyAuthenticationHandler(
        IOptionsMonitor<AuthenticationSchemeOptions> options,
        ILoggerFactory logger,
        UrlEncoder encoder,
        IConfiguration configuration)
        : base(options, logger, encoder)
    {
        _configuration = configuration;
    }

    protected override Task<AuthenticateResult> HandleAuthenticateAsync()
    {
        string? expectedKey = GetConfiguredKey();
        if (string.IsNullOrWhiteSpace(expectedKey))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        string? suppliedKey = GetSuppliedKey();
        if (string.IsNullOrWhiteSpace(suppliedKey))
        {
            return Task.FromResult(AuthenticateResult.NoResult());
        }

        if (!FixedTimeEquals(expectedKey.Trim(), suppliedKey.Trim()))
        {
            return Task.FromResult(AuthenticateResult.Fail("Invalid registry control credential."));
        }

        var claims = new[]
        {
            new Claim(ClaimTypes.NameIdentifier, "registry-control"),
            new Claim(ClaimTypes.Name, "registry-control"),
            new Claim("scope", RegistryAuthorization.ControlPolicy)
        };
        var identity = new ClaimsIdentity(claims, RegistryAuthorization.Scheme);
        var principal = new ClaimsPrincipal(identity);
        var ticket = new AuthenticationTicket(principal, RegistryAuthorization.Scheme);

        return Task.FromResult(AuthenticateResult.Success(ticket));
    }

    private string? GetConfiguredKey()
        => RegistryAuthorization.GetConfiguredControlCredential(_configuration);

    private string? GetSuppliedKey()
    {
        if (Request.Headers.TryGetValue(RegistryAuthorization.HeaderName, out var headerValues))
        {
            string? headerValue = headerValues.FirstOrDefault();
            if (!string.IsNullOrWhiteSpace(headerValue))
            {
                return headerValue;
            }
        }

        if (!Request.Headers.TryGetValue("Authorization", out var authorizationValues))
        {
            return null;
        }

        string? authorization = authorizationValues.FirstOrDefault();
        const string bearerPrefix = "Bearer ";
        return !string.IsNullOrWhiteSpace(authorization)
               && authorization.StartsWith(bearerPrefix, StringComparison.OrdinalIgnoreCase)
            ? authorization[bearerPrefix.Length..]
            : null;
    }

    private static bool FixedTimeEquals(string expected, string supplied)
    {
        byte[] expectedBytes = Encoding.UTF8.GetBytes(expected);
        byte[] suppliedBytes = Encoding.UTF8.GetBytes(supplied);
        return expectedBytes.Length == suppliedBytes.Length
               && CryptographicOperations.FixedTimeEquals(expectedBytes, suppliedBytes);
    }
}

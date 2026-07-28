# syntax=docker/dockerfile:1.7
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
ARG CHUMMER_BUILD_CONCURRENCY=1
WORKDIR /src

COPY Directory.Build.props Directory.Build.targets ./
COPY Chummer.Hub.Registry.Contracts/Chummer.Hub.Registry.Contracts.csproj Chummer.Hub.Registry.Contracts/
COPY Chummer.Run.Registry/Chummer.Run.Registry.csproj Chummer.Run.Registry/
RUN dotnet restore Chummer.Run.Registry/Chummer.Run.Registry.csproj

COPY Chummer.Hub.Registry.Contracts/ Chummer.Hub.Registry.Contracts/
COPY Chummer.Run.Registry/ Chummer.Run.Registry/
RUN nice -n 10 dotnet publish Chummer.Run.Registry/Chummer.Run.Registry.csproj \
    -c Release \
    -o /app/publish \
    --no-restore \
    --nologo \
    -m:${CHUMMER_BUILD_CONCURRENCY} \
    -p:BuildInParallel=false \
    -p:UseSharedCompilation=false

FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
ARG CHUMMER_RUNTIME_UID=1657
ARG CHUMMER_RUNTIME_GID=1657
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --gid "${CHUMMER_RUNTIME_GID}" chummer-registry \
 && useradd --uid "${CHUMMER_RUNTIME_UID}" --gid "${CHUMMER_RUNTIME_GID}" \
      --home-dir /nonexistent --shell /usr/sbin/nologin chummer-registry
COPY --from=build /app/publish .
RUN set -eu; \
    link="$(find -P /app -xdev -type l -print -quit)"; \
    test -z "$link"; \
    find -P /app -xdev -type d -exec chmod 0755 {} +; \
    find -P /app -xdev -type f -exec chmod 0644 {} +; \
    mkdir -p /app/state; \
    chown -R "${CHUMMER_RUNTIME_UID}:${CHUMMER_RUNTIME_GID}" /app/state; \
    chmod 0700 /app/state

ENV ASPNETCORE_URLS=http://+:8080
USER ${CHUMMER_RUNTIME_UID}:${CHUMMER_RUNTIME_GID}
ENTRYPOINT ["/bin/sh", "-c", "umask 077 && exec dotnet Chummer.Run.Registry.dll"]

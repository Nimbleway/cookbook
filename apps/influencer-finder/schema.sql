-- Influencer Finder — Supabase table (run once in the Supabase SQL editor)
create table if not exists influencers (
    platform            text not null,
    handle              text not null,
    category            text,
    profile_url         text,
    follower_count      text,
    follower_count_num  bigint,
    engagement_rate     text,
    niche               text,
    location            text,
    contact             text,
    bio_summary         text,
    query               text,
    observed_at         text,
    primary key (platform, handle)
);

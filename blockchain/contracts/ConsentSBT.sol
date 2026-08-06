// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @title HALAH Consent Soulbound Token
/// @notice Local proof-of-concept registry for time-bound patient consent.
contract ConsentSBT is ERC721, Ownable {
    uint256 private _nextTokenId;

    struct Consent {
        address patient;
        address requester;
        bytes32 consentHash;
        string purpose;
        uint64 validFrom;
        uint64 validUntil;
        bool revoked;
    }

    mapping(uint256 => Consent) public consents;
    mapping(bytes32 => uint256) public tokenByConsentHash;

    event ConsentIssued(
        uint256 indexed tokenId,
        bytes32 indexed consentHash,
        address indexed patient,
        address requester,
        uint64 validFrom,
        uint64 validUntil
    );

    event ConsentRevoked(
        uint256 indexed tokenId,
        bytes32 indexed consentHash,
        uint256 revokedAt
    );

    constructor() ERC721("HALAH Medical Consent", "HALAH-CONSENT") {}

    function mintConsent(
        address patient,
        address requester,
        bytes32 consentHash,
        string calldata purpose,
        uint64 validFrom,
        uint64 validUntil
    ) external onlyOwner returns (uint256 tokenId) {
        require(patient != address(0), "Invalid patient");
        require(requester != address(0), "Invalid requester");
        require(consentHash != bytes32(0), "Invalid consent hash");
        require(validUntil > validFrom, "Invalid validity window");
        require(tokenByConsentHash[consentHash] == 0, "Consent already minted");

        tokenId = ++_nextTokenId;
        _safeMint(patient, tokenId);

        consents[tokenId] = Consent({
            patient: patient,
            requester: requester,
            consentHash: consentHash,
            purpose: purpose,
            validFrom: validFrom,
            validUntil: validUntil,
            revoked: false
        });
        tokenByConsentHash[consentHash] = tokenId;

        emit ConsentIssued(
            tokenId,
            consentHash,
            patient,
            requester,
            validFrom,
            validUntil
        );
    }

    function revoke(uint256 tokenId) external onlyOwner {
        require(_exists(tokenId), "Unknown token");
        Consent storage consent = consents[tokenId];
        require(!consent.revoked, "Already revoked");
        consent.revoked = true;
        emit ConsentRevoked(tokenId, consent.consentHash, block.timestamp);
    }

    function checkValid(uint256 tokenId) public view returns (bool) {
        if (!_exists(tokenId)) return false;
        Consent memory consent = consents[tokenId];
        return
            !consent.revoked &&
            block.timestamp >= consent.validFrom &&
            block.timestamp <= consent.validUntil;
    }

    function checkAccess(uint256 tokenId, address requester)
        external
        view
        returns (bool)
    {
        return checkValid(tokenId) && consents[tokenId].requester == requester;
    }

    /// @dev Soulbound behaviour: minting and burning are allowed; transfers are not.
    function _beforeTokenTransfer(
        address from,
        address to,
        uint256 firstTokenId,
        uint256 batchSize
    ) internal override {
        require(from == address(0) || to == address(0), "Soulbound token");
        super._beforeTokenTransfer(from, to, firstTokenId, batchSize);
    }
}